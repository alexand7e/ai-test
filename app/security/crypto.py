from typing import Optional

from cryptography.fernet import Fernet


def _get_fernet(key: Optional[str]) -> Fernet:
    if not key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return Fernet(key.encode("utf-8"))


def encrypt_str(value: str, key: Optional[str]) -> str:
    f = _get_fernet(key)
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_str(value: str, key: Optional[str]) -> str:
    f = _get_fernet(key)
    return f.decrypt(value.encode("utf-8")).decode("utf-8")

