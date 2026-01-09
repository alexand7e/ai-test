"""Middleware de autenticação"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware para autenticação via token"""
    
    def __init__(self, app, access_token: str):
        super().__init__(app)
        self.access_token = access_token
    
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
        
        # Se não tiver token configurado, permite acesso (modo desenvolvimento)
        if not self.access_token:
            logger.warning("ACESS_TOKEN not configured, allowing access")
            return await call_next(request)
        
        # Verifica token
        if not token or token != self.access_token:
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

