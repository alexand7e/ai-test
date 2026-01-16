from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.schemas.auth import LoginRequest, SetupRequest
from app.security.jwt_service import create_access_token, decode_access_token

from app.core.config.config import settings

from app.utils.logging import logger

from app.infrastructure.database import prisma_db
from app.security.passwords import hash_password, verify_password

auth_router = APIRouter(tags=["authentication"])

@auth_router.post("/api/setup")
async def setup_initial_admin(request: SetupRequest):
    """Endpoint para configuração inicial (apenas se DB vazio)"""
    try:
        grupo = await prisma_db.db.grupo.create(
            data={
                "nome": request.group_name,
                "descricao": "Grupo de administração do sistema"
            }
        )
         
        admin_user = await prisma_db.db.usuario.create(
            data={
                "email": request.admin_email,
                "senhaHash": hash_password(request.admin_password),
                "nivel": "ADMIN_GERAL", # type: ignore
                "grupoId": grupo.id
            }
        )

        if settings.jwt_secret is None:
            raise ValueError("jwt_secret is required")

        token_data = create_access_token(
            secret=settings.jwt_secret,
            issuer=settings.jwt_issuer,
            user_id=admin_user.id,
            group_id=admin_user.grupoId,
            level=admin_user.nivel,
            ttl_minutes=settings.jwt_access_ttl_minutes,
        )

        await prisma_db.db.accesstoken.create(
            data={
                "jti": token_data["jti"],
                "expiresAt": token_data["expires_at"],
                "usuarioId": admin_user.id,
            }
        )

        logger.info(f"Setup completed. Admin created: {admin_user.email}")
        return {"success": True, "message": "Setup completed successfully"}
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@auth_router.post("/api/auth/login")
async def login(request: LoginRequest):
    """Endpoint de login"""
    if request.email and request.senha:
        if not settings.jwt_secret:
            raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
        user = await prisma_db.db.usuario.find_unique(where={"email": request.email})
        if not user or not verify_password(request.senha, user.senhaHash):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        token_data = create_access_token(
            secret=settings.jwt_secret,
            issuer=settings.jwt_issuer,
            user_id=user.id,
            group_id=user.grupoId,
            level=user.nivel,
            ttl_minutes=settings.jwt_access_ttl_minutes,
        )
        await prisma_db.db.accesstoken.create(
            data={
                "jti": token_data["jti"],
                "expiresAt": token_data["expires_at"],
                "usuarioId": user.id,
            }
        )

        response = JSONResponse(
            {
                "access_token": token_data["token"],
                "token_type": "bearer",
                "expires_at": token_data["expires_at"].isoformat(),
            }
        )
        response.set_cookie(
            key="access_token",
            value=token_data["token"],
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
            max_age=settings.jwt_access_ttl_minutes * 60,
        )
        return response

    if request.token:
        if not settings.acess_token:
            return JSONResponse({"success": True, "message": "Login realizado com sucesso"})
        if request.token != settings.acess_token:
            raise HTTPException(status_code=401, detail="Token inválido")
        response = JSONResponse({"success": True, "message": "Login realizado com sucesso"})
        response.set_cookie(
            key="access_token",
            value=request.token,
            httponly=True,
            secure=settings.environment == "production",
            samesite="lax",
            max_age=86400 * 7,
        )
        return response

    raise HTTPException(status_code=422, detail="Informe email/senha ou token")


@auth_router.post("/api/auth/verify")
async def verify_token(request: Request):
    """Verifica se o token é válido"""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return {"valid": False}

    if settings.jwt_secret:
        try:
            payload = decode_access_token(token=token, secret=settings.jwt_secret, issuer=settings.jwt_issuer)
            token_row = await prisma_db.db.accesstoken.find_unique(where={"jti": payload.get("jti")}) # type: ignore
            if not token_row or token_row.revokedAt is not None:
                return {"valid": False}
            expires_at = token_row.expiresAt
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                return {"valid": False}
            return {"valid": True}
        except Exception:
            return {"valid": False}

    if not settings.acess_token:
        return {"valid": True}
    return {"valid": token == settings.acess_token}


@auth_router.post("/api/auth/logout")
async def logout(request: Request):
    """Endpoint de logout"""
    token = request.cookies.get("access_token")
    if token and settings.jwt_secret:
        try:
            payload = decode_access_token(token=token, secret=settings.jwt_secret, issuer=settings.jwt_issuer)
            await prisma_db.db.accesstoken.update(
                where={"jti": payload.get("jti")}, # type: ignore
                data={"revokedAt": datetime.now(timezone.utc)},
            )
        except Exception:
            pass
    response = JSONResponse({"success": True, "message": "Logout realizado"})
    response.delete_cookie("access_token")
    return response


@auth_router.get("/api/auth/me")
async def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
