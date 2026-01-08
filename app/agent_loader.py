import yaml
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional
from app.models import AgentConfig
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class AgentLoader:
    """Carrega e gerencia configurações de agentes"""
    
    def __init__(self, agents_dir: Optional[str] = None):
        self.agents_dir = Path(agents_dir or settings.agents_dir)
        self.agents: Dict[str, AgentConfig] = {}
        self.webhook_map: Dict[str, str] = {}  # webhook_name -> agent_id
        self._load_all_agents()
    
    def _load_all_agents(self):
        """Carrega todos os agentes do diretório"""
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory {self.agents_dir} does not exist. Creating it.")
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            return
        
        # Limpa mapeamento antes de recarregar
        self.webhook_map.clear()
        
        for file_path in self.agents_dir.iterdir():
            if file_path.suffix in ['.yaml', '.yml', '.json']:
                try:
                    agent = self._load_agent(file_path)
                    if agent:
                        self.agents[agent.id] = agent
                        logger.info(f"Loaded agent: {agent.id}")
                except Exception as e:
                    logger.error(f"Error loading agent from {file_path}: {e}")
    
    def _load_agent(self, file_path: Path) -> Optional[AgentConfig]:
        """Carrega um agente de um arquivo YAML ou JSON"""
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        agent = AgentConfig(**data)
        
        # Atualiza mapeamento de webhook_name
        if agent.webhook_name:
            self.webhook_map[agent.webhook_name] = agent.id
        
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Retorna a configuração de um agente"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> Dict[str, AgentConfig]:
        """Lista todos os agentes carregados"""
        return self.agents.copy()
    
    def reload(self):
        """Recarrega todos os agentes"""
        self.agents.clear()
        self.webhook_map.clear()
        self._load_all_agents()
    
    def reload_agent(self, agent_id: str) -> bool:
        """Recarrega um agente específico"""
        # Remove webhook_name antigo do mapeamento se existir
        old_agent = self.agents.get(agent_id)
        if old_agent and old_agent.webhook_name:
            self.webhook_map.pop(old_agent.webhook_name, None)
        
        for file_path in self.agents_dir.iterdir():
            if file_path.suffix in ['.yaml', '.yml', '.json']:
                try:
                    agent = self._load_agent(file_path)
                    if agent and agent.id == agent_id:
                        self.agents[agent_id] = agent
                        logger.info(f"Reloaded agent: {agent_id}")
                        return True
                except Exception as e:
                    logger.error(f"Error reloading agent from {file_path}: {e}")
        return False
    
    def get_agent_by_webhook_name(self, webhook_name: str) -> Optional[AgentConfig]:
        """Retorna um agente pelo nome do webhook"""
        agent_id = self.webhook_map.get(webhook_name)
        if agent_id:
            return self.agents.get(agent_id)
        return None
    
    def _validate_agent_id(self, agent_id: str) -> bool:
        """Valida se o ID do agente é válido (apenas alfanuméricos, hífen, underscore)"""
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', agent_id))
    
    def _validate_webhook_name(self, webhook_name: str) -> bool:
        """Valida se o nome do webhook é válido (apenas alfanuméricos, hífen, underscore)"""
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', webhook_name))
    
    def save_agent(self, agent_config: AgentConfig) -> bool:
        """Salva um agente em arquivo YAML"""
        try:
            # Valida ID do agente
            if not self._validate_agent_id(agent_config.id):
                logger.error(f"Invalid agent ID: {agent_config.id}")
                return False
            
            # Valida webhook_name se fornecido
            if agent_config.webhook_name:
                if not self._validate_webhook_name(agent_config.webhook_name):
                    logger.error(f"Invalid webhook name: {agent_config.webhook_name}")
                    return False
                
                # Verifica se webhook_name já está em uso por outro agente
                existing_agent_id = self.webhook_map.get(agent_config.webhook_name)
                if existing_agent_id and existing_agent_id != agent_config.id:
                    logger.error(f"Webhook name already in use: {agent_config.webhook_name}")
                    return False
            
            # Prepara dados para salvar (remove None values opcionais para manter YAML limpo)
            data = agent_config.dict(exclude_none=False)
            
            # Salva arquivo YAML
            file_path = self.agents_dir / f"{agent_config.id}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            # Atualiza cache e mapeamento
            self.agents[agent_config.id] = agent_config
            if agent_config.webhook_name:
                self.webhook_map[agent_config.webhook_name] = agent_config.id
            
            logger.info(f"Saved agent: {agent_config.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving agent: {e}", exc_info=True)
            return False
    
    def delete_agent(self, agent_id: str) -> bool:
        """Remove um agente"""
        try:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found: {agent_id}")
                return False
            
            # Remove webhook_name do mapeamento se existir
            if agent.webhook_name:
                self.webhook_map.pop(agent.webhook_name, None)
            
            # Remove arquivo
            file_path = self.agents_dir / f"{agent_id}.yaml"
            if file_path.exists():
                file_path.unlink()
            
            # Remove do cache
            self.agents.pop(agent_id, None)
            
            logger.info(f"Deleted agent: {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting agent: {e}", exc_info=True)
            return False

