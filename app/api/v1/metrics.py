from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_container
from app.core.container import Container

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])

@metrics_router.get("/agents/{agent_id}")
async def get_agent_metrics(agent_id: str, days: int = 7, container: Container = Depends(get_container)):
    """Obtém métricas de um agente"""
    if not container.metrics_service:
        raise HTTPException(status_code=503, detail="Metrics service not initialized")
    
    return await container.metrics_service.get_agent_metrics(agent_id, days)


@metrics_router.get("/global")
async def get_global_metrics(days: int = 7, container: Container = Depends(get_container)):
    """Obtém métricas globais"""
    if not container.metrics_service:
        raise HTTPException(status_code=503, detail="Metrics service not initialized")
    
    return await container.metrics_service.get_global_metrics(days)
