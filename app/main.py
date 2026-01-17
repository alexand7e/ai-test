from app.api.v1.webhooks import webhook_router
from app.api.v1.rag import rag_router
from app.api.v1.metrics import metrics_router
from app.api.v1.groups import group_router
from app.api.v1.auth import auth_router
from app.api.v1.admin import admin_router
from app.api.v1.agents import agents_router, grupo_agents_router

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.dependencies import get_container

from contextlib import asynccontextmanager

from app.infrastructure.cache.redis_client import RedisClient
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.auth_middleware import AuthMiddleware

from app.core.container import Container
from app.core.config.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = await Container.create()
    app.state.container = container

    yield

    await container.cleanup()

app = FastAPI(
    title="AI Agent API",
    description="API para agentes de IA com RAG e webhooks",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Autenticação
app.add_middleware(
    AuthMiddleware,
    access_token=settings.acess_token,
    jwt_secret=settings.jwt_secret,
    jwt_issuer=settings.jwt_issuer
)

# Rate Limiting
app.add_middleware(
    RateLimiterMiddleware,
    redis_client=RedisClient(),
    # Use lazy init or just new instance. RedisClient handles its own pool.
    requests_per_minute=60
)

@app.get("/")
async def root():
    return "root"


@app.get("/health")
async def health_check(container: Container = Depends(get_container)):
    """Health check endpoint"""
    redis_ok = await container.redis_client.ping() if container.redis_client else False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "agents_loaded": len(container.agent_loader.list_agents()) if container.agent_loader else 0
    }

app.include_router(webhook_router)  # /webhooks/*

app.include_router(auth_router)  # /auth/* e /api/auth/* e /api/setup

app.include_router(agents_router)  # /agents/*
app.include_router(grupo_agents_router)  # /api/grupo/agentes/*
app.include_router(rag_router)  # /rag/*
app.include_router(metrics_router)  # /metrics/*
app.include_router(admin_router)  # /api/admin/* (usuarios, dashboard)
app.include_router(group_router)  # /api/admin/grupos/*
