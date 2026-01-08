"""Middleware de rate limiting"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.infrastructure.redis_client import RedisClient
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware para rate limiting baseado em IP"""
    
    def __init__(self, app, redis_client: RedisClient, requests_per_minute: int = 60):
        super().__init__(app)
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
    
    async def dispatch(self, request: Request, call_next):
        # Ignora rate limiting para health check e endpoints de admin
        if request.url.path in ["/health", "/admin", "/static"] or request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Obtém IP do cliente
        client_ip = request.client.host if request.client else "unknown"
        
        # Verifica rate limit
        if await self._check_rate_limit(client_ip):
            return await call_next(request)
        else:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
            )
    
    async def _check_rate_limit(self, client_ip: str) -> bool:
        """Verifica se o IP pode fazer mais requisições"""
        if not self.redis.client:
            return True  # Se Redis não estiver disponível, permite
        
        try:
            key = f"ratelimit:{client_ip}"
            current = await self.redis.client.get(key)
            
            if current is None:
                # Primeira requisição
                await self.redis.client.setex(key, 60, "1")
                return True
            
            count = int(current)
            if count >= self.requests_per_minute:
                return False
            
            # Incrementa contador
            await self.redis.client.incr(key)
            return True
        
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True  # Em caso de erro, permite

