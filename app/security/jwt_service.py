from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import uuid

import jwt


def create_access_token(*, secret: str, issuer: str, user_id: str, group_id: str, level: str, ttl_minutes: int) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)
    jti = str(uuid.uuid4())
    payload = {
        "iss": issuer,
        "sub": user_id,
        "grp": group_id,
        "lvl": level,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"token": token, "jti": jti, "expires_at": expires_at}


def decode_access_token(*, token: str, secret: str, issuer: str) -> Dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"], issuer=issuer, options={"require": ["exp", "iat", "iss", "sub", "jti"]})

