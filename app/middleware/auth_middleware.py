from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from datetime import datetime, timezone
import re

from app.infrastructure.database import prisma_db
from app.security.jwt_service import decode_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        access_token: str | None = None,
        jwt_secret: str | None = None,
        jwt_issuer: str = "ai-agent-api",
    ):
        super().__init__(app)
        self.access_token = access_token
        self.jwt_secret = jwt_secret
        self.jwt_issuer = jwt_issuer

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Rotas completamente públicas (sem autenticação)
        public_patterns = [
            r"^/webhooks",                    # Webhooks públicos
            r"^/static",                      # Arquivos estáticos
            r"^/docs",                        # Documentação
            r"^/openapi\.json$",              # OpenAPI spec
            r"^/redoc",                       # ReDoc
            r"^/api/setup$",                  # Setup inicial
            r"^/api/auth/login$",             # Login
            r"^/api/auth/verify$",            # Verificar token
            r"^/auth/login$",                 # Página de login
            r"^/auth/signup$",                # Página de signup
        ]

        for pattern in public_patterns:
            if re.match(pattern, path):
                return await call_next(request)

        # 2. Rotas protegidas que requerem autenticação
        protected_patterns = [
            r"^/api/(?!setup|auth/login|auth/verify)",  # Todas /api/* exceto setup e login
            r"^/agents",                                  # Todas /agents/*
            r"^/metrics",                                 # Todas /metrics/*
            r"^/rag",                                     # Todas /rag/*
        ]

        is_protected = False
        for pattern in protected_patterns:
            if re.match(pattern, path):
                is_protected = True
                break

        # 3. Se é rota protegida, verificar autenticação
        if is_protected:
            # Tentar obter token
            token = request.cookies.get("access_token")
            if not token:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]

            if not token:
                # Se é requisição de API, retorna 401
                if path.startswith("/api/") or path.startswith("/agents") or path.startswith("/metrics") or path.startswith("/rag"):
                    return JSONResponse(
                        {"detail": "Not authenticated"},
                        status_code=401
                    )
                # Se é navegador, redireciona para login
                return RedirectResponse(url="/auth/login")

            # Validar token
            user_data = None

            # Tentar validar com JWT
            if self.jwt_secret:
                try:
                    payload = decode_access_token(
                        token=token,
                        secret=self.jwt_secret,
                        issuer=self.jwt_issuer
                    )
                    
                    # Verificar se token existe e não foi revogado
                    token_row = await prisma_db.db.accesstoken.find_unique(
                        where={"jti": payload.get("jti")}
                    )
                    
                    if not token_row or token_row.revokedAt is not None:
                        raise ValueError("Token revoked")
                    
                    # Verificar expiração
                    expires_at = token_row.expiresAt
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    
                    if expires_at <= datetime.now(timezone.utc):
                        raise ValueError("Token expired")
                    
                    # Obter dados do usuário
                    usuario = await prisma_db.db.usuario.find_unique(
                        where={"id": payload.get("sub")}
                    )
                    
                    if usuario:
                        user_data = {
                            "id": usuario.id,
                            "email": usuario.email,
                            "nivel": usuario.nivel,
                            "grupoId": usuario.grupoId
                        }
                        
                except Exception:
                    pass

            # Se JWT falhou, tentar token simples
            if not user_data and self.access_token:
                if token == self.access_token:
                    user_data = {
                        "id": "system",
                        "email": "system@admin",
                        "nivel": "ADMIN_GERAL",
                        "grupoId": None
                    }

            # Se não conseguiu validar, negar acesso
            if not user_data:
                if path.startswith("/api/") or path.startswith("/agents") or path.startswith("/metrics") or path.startswith("/rag"):
                    return JSONResponse(
                        {"detail": "Invalid or expired token"},
                        status_code=401
                    )
                return RedirectResponse(url="/auth/login")

            # Adicionar usuário ao request.state
            request.state.user = user_data

        # 4. Rota raiz (/) - redirecionar baseado em autenticação
        if path == "/":
            token = request.cookies.get("access_token")
            if not token:
                return RedirectResponse(url="/auth/login")

        # Continuar com a requisição
        return await call_next(request)
