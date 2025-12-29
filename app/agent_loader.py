import yaml
import json
import os
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
        self._load_all_agents()
    
    def _load_all_agents(self):
        """Carrega todos os agentes do diretório"""
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory {self.agents_dir} does not exist. Creating it.")
            self.agents_dir.mkdir(parents=True, exist_ok=True)
            return
        
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
        
        return AgentConfig(**data)
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Retorna a configuração de um agente"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> Dict[str, AgentConfig]:
        """Lista todos os agentes carregados"""
        return self.agents.copy()
    
    def reload(self):
        """Recarrega todos os agentes"""
        self.agents.clear()
        self._load_all_agents()
    
    def reload_agent(self, agent_id: str) -> bool:
        """Recarrega um agente específico"""
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

