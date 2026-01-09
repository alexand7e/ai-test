from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenAI (ou API compatível)
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    agents_dir: str = "./agents"
    redis_queue_name: str = "agent_jobs"
    redis_stream_name: str = "agent_stream"
    
    # Security
    acess_token: str = ""  # Token de acesso para autenticação
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

