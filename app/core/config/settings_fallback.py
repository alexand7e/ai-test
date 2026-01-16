import os
from typing import Optional

class FallbackSettings:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.agents_dir = os.getenv("AGENTS_DIR", "./agents")
        self.redis_queue_name = os.getenv("REDIS_QUEUE_NAME", "agent_jobs")
        self.redis_stream_name = os.getenv("REDIS_STREAM_NAME", "agent_stream")
        self.acess_token = os.getenv("ACESS_TOKEN", "")
        self.database_url = self._normalize_database_url(os.getenv("DATABASE_URL"))
        self.jwt_secret = os.getenv("JWT_SECRET") or None
        self.jwt_issuer = os.getenv("JWT_ISSUER", "ai-agent-api")
        self.jwt_access_ttl_minutes = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "60"))
        self.encryption_key = os.getenv("ENCRYPTION_KEY") or None
        self.migrate_on_startup = (os.getenv("MIGRATE_ON_STARTUP", "true").strip().lower() in {"1", "true", "yes", "y"})
        
        self.migrate_on_startup = (os.getenv("MIGRATE_ON_STARTUP", "true").strip().lower() in {"1", "true", "yes", "y"})

    @staticmethod
    def _normalize_database_url(v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        value = v.strip()
        if not value:
            return None
        if value.lower().startswith("psql "):
            value = value[5:].strip()
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            value = value[1:-1]
        return value
