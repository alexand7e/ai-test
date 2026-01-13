import yaml
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Any, List
from app.models import AgentConfig
from app.config import settings
from app.infrastructure import prisma_db
from app.security.crypto import decrypt_str
import logging

logger = logging.getLogger(__name__)


class AgentLoader:
    """Carrega e gerencia configurações de agentes"""
    
    def __init__(self, agents_dir: Optional[str] = None):
        self.agents_dir = Path(agents_dir or settings.agents_dir)
        self.agents: Dict[str, AgentConfig] = {}
        self.webhook_map: Dict[str, str] = {}  # webhook_name -> agent_id
        # Note: Initialization is now async via load_all_agents()
    
    async def load_all_agents(self):
        """Carrega todos os agentes (Arquivos + Banco de Dados)"""
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory {self.agents_dir} does not exist. Creating it.")
            self.agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Limpa mapeamentos
        self.agents.clear()
        self.webhook_map.clear()
        
        # 1. Carrega de arquivos (Legado/Dev) - Síncrono por natureza de IO local, mas OK em startup
        await self._load_from_files()
        
        # 2. Carrega do Banco de Dados (Produção/Dinâmico)
        await self._load_from_db()
        
        logger.info(f"Total agents loaded: {len(self.agents)}")

    async def _load_from_files(self):
        """Carrega agentes do sistema de arquivos"""
        for file_path in self.agents_dir.iterdir():
            if file_path.suffix in ['.yaml', '.yml', '.json']:
                try:
                    agent = self._load_agent_file(file_path)
                    if agent:
                        self.agents[agent.id] = agent
                        if agent.webhook_name:
                            self.webhook_map[agent.webhook_name] = agent.id
                        logger.info(f"Loaded file agent: {agent.id}")
                except Exception as e:
                    logger.error(f"Error loading agent from {file_path}: {e}")

    def _load_agent_file(self, file_path: Path) -> Optional[AgentConfig]:
        """Lê um arquivo de agente"""
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        return AgentConfig(**data)

    async def _load_from_db(self):
        """Busca agentes no banco de dados Prisma"""
        try:
            db_agents = await prisma_db.db.agente.find_many()
            for db_agent in db_agents:
                try:
                    # Decrypt and construct config
                    config_data = self._decrypt_config(db_agent.configuracoes)
                    
                    # Ensure ID and Nome match the DB record
                    config_data['id'] = db_agent.id
                    if db_agent.nome:
                         config_data['nome'] = db_agent.nome
                    if db_agent.grupoId:
                         config_data['grupoId'] = db_agent.grupoId
                         
                    # Create AgentConfig object
                    agent = AgentConfig(**config_data)
                    
                    self.agents[agent.id] = agent
                    if agent.webhook_name:
                         self.webhook_map[agent.webhook_name] = agent.id
                         
                    logger.info(f"Loaded DB agent: {agent.id}")
                except Exception as e:
                    logger.error(f"Error loading agent {db_agent.id} from DB: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch agents from DB: {e}")

    def _decrypt_config(self, value: Any) -> Any:
        """Recursively decrypts config values"""
        if isinstance(value, dict):
             return {k: self._decrypt_config(v) for k, v in value.items()}
        elif isinstance(value, list):
             return [self._decrypt_config(v) for v in value]
        elif isinstance(value, str):
             if value.startswith("enc:") and settings.encryption_key:
                 try:
                     return decrypt_str(value[4:], settings.encryption_key)
                 except Exception:
                     # If decryption fails, return original (or empty?)
                     logger.warning("Failed to decrypt value, returning original")
                     return value
        return value

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        return self.agents.get(agent_id)
    
    def list_agents(self) -> Dict[str, AgentConfig]:
        return self.agents.copy()
    
    async def reload(self):
        """Recarrega todos os agentes assincronamente"""
        await self.load_all_agents()
    
    async def reload_agent(self, agent_id: str) -> bool:
        """Recarrega um agente específico (Re-lê tudo por enquanto para simplificar ou busca específico)"""
        # For simplicity and correctness with DB, we'll reload all. 
        # Making granular update requires checking if it's file or DB.
        # Given the content, reloading all is safer to sync properly.
        await self.load_all_agents()
        return agent_id in self.agents
    
    def get_agent_by_webhook_name(self, webhook_name: str) -> Optional[AgentConfig]:
        agent_id = self.webhook_map.get(webhook_name)
        if agent_id:
            return self.agents.get(agent_id)
        return None
    
    def _validate_agent_id(self, agent_id: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', agent_id))
    
    def _validate_webhook_name(self, webhook_name: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', webhook_name))
    
    def save_agent(self, agent_config: AgentConfig) -> bool:
        """Salva agente. OBS: Atualmente salva apenas em ARQUIVO.
           TODO: Atualizar para salvar no DB se a origem for DB?
           Por enquanto mantemos o comportamento de salvar em arquivo para compatibilidade.
        """
        # ... (Mantém lógica existente para arquivo por compatibilidade da API existente)
        try:
            if not self._validate_agent_id(agent_config.id):
                logger.error(f"Invalid agent ID: {agent_config.id}")
                return False
            
            if agent_config.webhook_name:
                if not self._validate_webhook_name(agent_config.webhook_name):
                    logger.error(f"Invalid webhook name: {agent_config.webhook_name}")
                    return False
                existing_agent_id = self.webhook_map.get(agent_config.webhook_name)
                if existing_agent_id and existing_agent_id != agent_config.id:
                    return False
            
            data = agent_config.dict(exclude_none=False)
            file_path = self.agents_dir / f"{agent_config.id}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            self.agents[agent_config.id] = agent_config
            if agent_config.webhook_name:
                self.webhook_map[agent_config.webhook_name] = agent_config.id
            
            return True
        except Exception as e:
            logger.error(f"Error saving agent: {e}")
            return False

    def delete_agent(self, agent_id: str) -> bool:
        """Remove agente (apenas arquivo por enquanto)"""
        # ... (Lógica existente)
        try:
            agent = self.agents.get(agent_id)
            if not agent: return False
            
            if agent.webhook_name:
                self.webhook_map.pop(agent.webhook_name, None)
            
            file_path = self.agents_dir / f"{agent_id}.yaml"
            if file_path.exists():
                file_path.unlink()
            
            self.agents.pop(agent_id, None)
            return True
        except Exception:
            return False
