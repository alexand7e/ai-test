"""Middleware de autenticação"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
from datetime import datetime, timezone

from app.infrastructure import prisma_db
from app.security.jwt_service import decode_access_token

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware para autenticação via token"""
    
    def __init__(self, app, access_token: str, jwt_secret: str | None = None, jwt_issuer: str = "ai-agent-api"):
        super().__init__(app)
        self.access_token = access_token
        self.jwt_secret = jwt_secret
        self.jwt_issuer = jwt_issuer
    
    async def dispatch(self, request: Request, call_next):
        # Endpoints públicos que não precisam de autenticação
        public_paths = [
            "/health",
            "/static",
            "/login",
            "/api/auth/login",
            "/api/auth/verify"
        ]
        
        # Verifica se o path é público
        is_public = any(
            request.url.path == path or 
            request.url.path.startswith(path + "/") or
            request.url.path.startswith("/static")
            for path in public_paths
        )
        
        if is_public:
            return await call_next(request)
        
        # Verifica autenticação via cookie ou header
        token = None
        
        # Tenta obter do cookie primeiro
        token = request.cookies.get("access_token")
        
        # Se não tiver no cookie, tenta no header
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if token and self.jwt_secret:
            try:
                payload = decode_access_token(token=token, secret=self.jwt_secret, issuer=self.jwt_issuer)
                jti = payload.get("jti")
                token_row = await prisma_db.db.accesstoken.find_unique(where={"jti": jti})
                if not token_row or token_row.revokedAt is not None:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revogado ou inválido")

                expires_at = token_row.expiresAt
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc):
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")

                request.state.user = {
                    "id": payload.get("sub"),
                    "grupoId": payload.get("grp"),
                    "nivel": payload.get("lvl"),
                    "jti": jti,
                }
                return await call_next(request)
            except HTTPException:
                raise
            except Exception:
                token = None

        # Se não tiver token configurado, permite acesso (modo desenvolvimento)
        if not self.access_token and not self.jwt_secret:
            logger.warning("No auth configured, allowing access")
            return await call_next(request)

        if not token or (self.access_token and token != self.access_token):
            # Se for requisição de API, retorna 401
            if request.url.path.startswith("/api/") or request.url.path.startswith("/webhooks/"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token de acesso inválido ou ausente"
                )
            # Se for página HTML, redireciona para login
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/login", status_code=302)
        
        return await call_next(request)

