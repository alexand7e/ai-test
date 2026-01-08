from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
# Rate limiting será implementado se necessário
# from app.middleware.rate_limiter import RateLimiterMiddleware

from app.config import settings
from app.models import WebhookMessage, MessageChannel
from app.agent_loader import AgentLoader
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.openai_client import OpenAIClient
from app.domain.rag_service import RAGService
from app.domain.agent_service import AgentService
from app.domain.metrics_service import MetricsService
from app.domain.rag_document_service import RAGDocumentService
from pydantic import BaseModel
from typing import Optional, Dict, Any
import time

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Instâncias globais
agent_loader: AgentLoader = None
redis_client: RedisClient = None
openai_client: OpenAIClient = None
agent_service: AgentService = None
metrics_service: MetricsService = None
rag_document_service: RAGDocumentService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    global agent_loader, redis_client, openai_client, agent_service
    global metrics_service, rag_document_service
    
    # Startup
    logger.info("Starting application...")
    
    # Inicializa componentes
    agent_loader = AgentLoader()
    redis_client = RedisClient()
    await redis_client.connect()
    
    openai_client = OpenAIClient()
    
    rag_service = RAGService(redis_client, openai_client)
    agent_service = AgentService(redis_client, openai_client, rag_service)
    metrics_service = MetricsService(redis_client)
    rag_document_service = RAGDocumentService(redis_client, openai_client)
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await redis_client.disconnect()
    logger.info("Application shut down")


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

# Rate Limiting será adicionado dinamicamente no lifespan

# Servir arquivos estáticos
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve a página inicial do chat"""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Agent API - Acesse /static/index.html"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_ok = await redis_client.ping() if redis_client else False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "agents_loaded": len(agent_loader.list_agents()) if agent_loader else 0
    }


@app.post("/webhooks/{agent_id}")
async def webhook_entry(agent_id: str, request: Request):
    """Endpoint de webhook para receber mensagens"""
    
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Verifica se o agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    start_time = time.time()
    success = False
    tokens_used = None
    
    try:
        # Parse do body (assumindo JSON)
        body = await request.json()
        
        # Normaliza mensagem (simplificado - em produção, validar conforme provedor)
        message = WebhookMessage(
            user_id=body.get("user_id", "unknown"),
            channel=MessageChannel(body.get("channel", "web")),
            text=body.get("text", ""),
            metadata=body.get("metadata", {}),
            conversation_id=body.get("conversation_id")
        )
        
        # Recupera histórico de mensagens do body ou do Redis
        history = body.get("history", [])
        
        # Verifica se deve usar streaming
        stream = body.get("stream", False)
        
        if stream:
            # Stream direto via SSE
            # Nota: Em streaming, não temos tokens até o final, então não registramos métricas aqui
            async def generate():
                nonlocal success
                try:
                    async for token in agent_service.process_message(
                        agent_config, message, stream=True, history=history
                    ):
                        yield f"data: {token}\n\n"
                    success = True
                except Exception as e:
                    logger.error(f"Error in stream: {e}", exc_info=True)
                    yield f"data: [ERRO: {str(e)}]\n\n"
                    success = False
            
            # Para streaming, não registramos métricas aqui pois não temos tokens
            # As métricas de streaming podem ser registradas no cliente ou via webhook
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        else:
            # Enfileira job para worker processar
            job_data = {
                "agent_id": agent_id,
                "message": message.dict(),
                "history": history,  # Incluir histórico no job
                "stream": False,
                "webhook_output_url": agent_config.webhook_output_url
            }
            
            job_id = await redis_client.enqueue_job(job_data)
            success = True
            
            return JSONResponse({
                "status": "enqueued",
                "job_id": job_id,
                "agent_id": agent_id
            })
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        success = False
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Registra métricas
        if metrics_service and not stream:
            response_time = time.time() - start_time
            await metrics_service.record_message(
                agent_id=agent_id,
                user_id=message.user_id if 'message' in locals() else "unknown",
                channel=message.channel.value if 'message' in locals() else "web",
                response_time=response_time,
                tokens_used=tokens_used,
                success=success
            )


@app.get("/agents")
async def list_agents():
    """Lista todos os agentes configurados"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agents = agent_loader.list_agents()
    return {
        "agents": [
            {
                "id": agent.id,
                "model": agent.model,
                "has_rag": agent.rag is not None,
                "tools_count": len(agent.tools)
            }
            for agent in agents.values()
        ]
    }


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Obtém detalhes de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    return agent_config.dict()


@app.post("/agents/{agent_id}/reload")
async def reload_agent(agent_id: str):
    """Recarrega um agente específico"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    success = agent_loader.reload_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    return {"status": "reloaded", "agent_id": agent_id}


@app.post("/agents/reload")
async def reload_all_agents():
    """Recarrega todos os agentes"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agent_loader.reload()
    return {"status": "reloaded", "count": len(agent_loader.list_agents())}


# ==================== MÉTRICAS ====================

@app.get("/metrics/agents/{agent_id}")
async def get_agent_metrics(agent_id: str, days: int = 7):
    """Obtém métricas de um agente"""
    if not metrics_service:
        raise HTTPException(status_code=503, detail="Metrics service not initialized")
    
    return await metrics_service.get_agent_metrics(agent_id, days)


@app.get("/metrics/global")
async def get_global_metrics(days: int = 7):
    """Obtém métricas globais"""
    if not metrics_service:
        raise HTTPException(status_code=503, detail="Metrics service not initialized")
    
    return await metrics_service.get_global_metrics(days)


# ==================== RAG DOCUMENTS ====================

class DocumentCreate(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None


@app.post("/rag/{index_name}/documents")
async def create_document(index_name: str, document: DocumentCreate):
    """Adiciona um documento ao índice RAG"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    try:
        doc_id = await rag_document_service.add_document(
            index_name=index_name,
            content=document.content,
            metadata=document.metadata
        )
        return {"status": "created", "document_id": doc_id, "index_name": index_name}
    except Exception as e:
        logger.error(f"Error creating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/{index_name}/documents")
async def list_documents(index_name: str, limit: int = 100):
    """Lista documentos de um índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    documents = await rag_document_service.list_documents(index_name, limit)
    return {"index_name": index_name, "documents": documents, "count": len(documents)}


@app.delete("/rag/{index_name}/documents/{document_id}")
async def delete_document(index_name: str, document_id: str):
    """Remove um documento do índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    success = await rag_document_service.delete_document(index_name, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "deleted", "document_id": document_id}


@app.get("/rag/{index_name}/stats")
async def get_index_stats(index_name: str):
    """Obtém estatísticas de um índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    return await rag_document_service.get_index_stats(index_name)


@app.post("/rag/{index_name}/search")
async def search_documents(index_name: str, query: str, top_k: int = 5):
    """Busca documentos similares"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    results = await rag_document_service.search_documents(index_name, query, top_k)
    return {"index_name": index_name, "query": query, "results": results}


# ==================== DASHBOARD ====================

@app.get("/admin")
async def admin_dashboard():
    """Serve o dashboard administrativo"""
    admin_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "static",
        "admin.html"
    )
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return {"message": "Admin dashboard not available"}

