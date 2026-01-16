from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import field_validator

class PydanticSettings(BaseSettings):
    openai_api_key: str = "teste"
    openai_base_url: str = "https://api.openai.com/v1"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    environment: str = "development"
    log_level: str = "INFO"
    agents_dir: str = "./agents"
    redis_queue_name: str = "agent_jobs"
    redis_stream_name: str = "agent_stream"
    acess_token: str = ""
    database_url: Optional[str] = None
    jwt_secret: Optional[str] = "teste_jwt"
    jwt_issuer: str = "ai-agent-api"
    jwt_access_ttl_minutes: int = 60
    encryption_key: Optional[str] = None
    migrate_on_startup: bool = True
    
    migrate_on_startup: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        value = v.strip()
        if not value:
            return None
        if value.lower().startswith("psql "):
            value = value[5:].strip()
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"
