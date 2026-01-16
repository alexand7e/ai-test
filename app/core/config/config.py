try:
    from app.core.config.settings_pydantic import PydanticSettings as Settings
except ImportError:
    from app.core.config.settings_fallback import FallbackSettings as Settings

settings = Settings()
