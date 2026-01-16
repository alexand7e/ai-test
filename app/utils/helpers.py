from typing import Any, Dict, List

from app.core.config.config import settings

from app.security.crypto import encrypt_str

def _encrypt_sensitive_config(value: Any) -> Any:
    if isinstance(value, dict):
        encrypted: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).lower()
            if isinstance(v, str) and settings.encryption_key and (
                key in {"password", "senha", "secret", "token", "api_key", "apikey"} or key.endswith("_key")
            ):
                encrypted[k] = "enc:" + encrypt_str(v, settings.encryption_key)
            else:
                encrypted[k] = _encrypt_sensitive_config(v)
        return encrypted
    if isinstance(value, list):
        return [_encrypt_sensitive_config(v) for v in value]
    return value


def _pgvector_literal(values: List[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"
