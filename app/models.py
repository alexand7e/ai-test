from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class MessageChannel(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SLACK = "slack"
    WEB = "web"


class WebhookMessage(BaseModel):
    """Mensagem normalizada de entrada via webhook"""
    user_id: str
    channel: MessageChannel
    text: str
    metadata: Optional[Dict[str, Any]] = {}
    conversation_id: Optional[str] = None


class Job(BaseModel):
    """Job enfileirado para processamento"""
    job_id: str
    agent_id: str
    message: WebhookMessage
    stream: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    webhook_output_url: Optional[str] = None


class AgentRAGConfig(BaseModel):
    """Configuração de RAG para um agente"""
    type: str = "redis"
    index_name: str
    top_k: int = 5
    documents_dir: Optional[str] = None
    chunk_size: int = 1500
    overlap: int = 300


class AgentTool(BaseModel):
    """Ferramenta disponível para um agente"""
    name: str
    type: str  # http, python_function, etc.
    url: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class DataAnalysisConfig(BaseModel):
    """Configuração de análise de dados para um agente"""
    enabled: bool = False
    files: List[str] = Field(default_factory=list)  # Lista de arquivos carregados (CSV, JSON, XLSX)
    query_engine: str = "pandas"  # Tipo de engine (pandas, etc)


class AgentConfig(BaseModel):
    """Configuração completa de um agente"""
    id: str
    nome: Optional[str] = None  # Nome exibido do agente
    model: str = "Qwen/Qwen2.5-3B-Instruct"
    api_key: Optional[str] = None  # API key específica do agente (opcional, informativo)
    webhook_name: Optional[str] = None  # Nome do webhook personalizado para /webhook/{webhook_name}
    system_prompt: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    rag: Optional[AgentRAGConfig] = None
    data_analysis: Optional[DataAnalysisConfig] = None
    tools: List[AgentTool] = Field(default_factory=list)
    webhook_output_url: Optional[str] = None


class RAGContext(BaseModel):
    """Contexto retornado da busca RAG"""
    content: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """Resposta do agente"""
    agent_id: str
    conversation_id: str
    response: str
    contexts: List[RAGContext] = Field(default_factory=list)
    tokens_used: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)

