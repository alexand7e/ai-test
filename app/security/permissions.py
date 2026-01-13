from fastapi import HTTPException, status, Request


def get_auth(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin_geral(request: Request) -> dict:
    user = get_auth(request)
    if user.get("nivel") != "ADMIN_GERAL":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return user


def require_admin_grupo(request: Request) -> dict:
    user = get_auth(request)
    if user.get("nivel") not in {"ADMIN", "ADMIN_GERAL"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return user

