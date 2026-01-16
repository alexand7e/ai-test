from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from datetime import datetime


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
