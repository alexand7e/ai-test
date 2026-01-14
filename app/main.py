from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
# Rate limiting será implementado se necessário
from app.middleware.rate_limiter import RateLimiterMiddleware
import bleach

from app.config import settings
from app.models import WebhookMessage, MessageChannel, AgentConfig, AgentRAGConfig, DataAnalysisConfig
from app.agent_loader import AgentLoader
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.qdrant_client import QdrantClient
from app.infrastructure.openai_client import OpenAIClient
from app.domain.rag_service import RAGService
from app.domain.agent_service import AgentService
from app.domain.metrics_service import MetricsService
from app.domain.rag_document_service import RAGDocumentService
from app.domain.data_analysis_service import DataAnalysisService
from app.middleware.auth_middleware import AuthMiddleware
from app.infrastructure import prisma_db
from app.infrastructure.migration_runner import apply_migrations
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import time
import json
import html
import json
import re
import hashlib
import tempfile
import uuid
from pathlib import Path


from app.domain.document_ingestion import extract_text, chunk_text
from app.security.passwords import verify_password, hash_password
from app.security.jwt_service import create_access_token, decode_access_token
from datetime import datetime, timezone
from app.security.permissions import get_auth, require_admin_geral, require_admin_grupo
from app.security.crypto import encrypt_str

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Instâncias globais
agent_loader: AgentLoader = None
redis_client = RedisClient()
qdrant_client: QdrantClient = None
openai_client: OpenAIClient = None
agent_service: AgentService = None
metrics_service: MetricsService = None
rag_document_service: RAGDocumentService = None
data_analysis_service: DataAnalysisService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    global agent_loader, redis_client, qdrant_client, openai_client, agent_service
    global metrics_service, rag_document_service, data_analysis_service
    
    # Startup
    logger.info("Starting application...")

    if settings.database_url:
        os.environ["DATABASE_URL"] = settings.database_url
        await prisma_db.connect()
        if settings.migrate_on_startup:
            await apply_migrations(prisma_db.db)
    
    # Inicializa componentes
    agent_loader = AgentLoader()
    await agent_loader.load_all_agents()
    # redis_client already instantiated globally
    await redis_client.connect()
    
    # Bootstrap Admin - REMOVED (Replaced by Interactive Setup)
    # Logic now resides in POST /api/setup


    qdrant_client = QdrantClient()
    await qdrant_client.connect()
    
    openai_client = OpenAIClient()
    
    rag_service = RAGService(redis_client, openai_client, qdrant_client=qdrant_client)
    data_analysis_service = DataAnalysisService()
    agent_service = AgentService(redis_client, openai_client, rag_service, data_analysis_service)
    metrics_service = MetricsService(redis_client)
    rag_document_service = RAGDocumentService(redis_client, openai_client, qdrant_client=qdrant_client)
    
    # Carrega arquivos de análise de dados para agentes existentes
    agents = agent_loader.list_agents()
    for agent_id, agent_config in agents.items():
        if agent_config.data_analysis and agent_config.data_analysis.enabled:
            if agent_config.data_analysis.files:
                data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        if qdrant_client:
            await qdrant_client.disconnect()
    except Exception:
        pass
    await redis_client.disconnect()
    try:
        await prisma_db.disconnect()
    except Exception:
        pass
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
    redis_client=redis_client, 
    # Use lazy init or just new instance. RedisClient handles its own pool.
    requests_per_minute=60
)

# Servir arquivos estáticos
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


## Devido ao middleware essa rota nunca é alcançada
@app.get("/")
async def root(request: Request):
    """Serve a página inicial do chat (ou Setup se DB vazio)"""
    return {"message": "Home"}
    ### Check if setup is needed
    #
    #try:
    #
    #    #### Improve: verificar por cookie do navegador
    #    #token = request.cookies.get("access_token")
    #    #if not token:
    #    user_count = await prisma_db.db.usuario.count()
    #    if user_count == 0:
    #        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    #        setup_path = os.path.join(static_dir, "setup.html")
    #        if os.path.exists(setup_path):
    #            return FileResponse(setup_path)
    #        return {"message": "Setup required. Please create initial admin."}
    #except Exception:
    #    pass
    #
    #static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    #index_path = os.path.join(static_dir, "index.html")
    #if os.path.exists(index_path):
    #    return FileResponse(index_path)
    #return {"message": "AI Agent API - Acesse /static/index.html"}


## Devido ao middleware essa rota nunca é alcançada
@app.get("/singup")
async def root():
    """Serve a página inicial do chat (ou Setup se DB vazio)"""
    # Check if setup is needed
    try:
        ### Bug
        user_count = await prisma_db.db.usuario.count()
        if user_count == 0:
            static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
            setup_path = os.path.join(static_dir, "setup.html")
            if os.path.exists(setup_path):
                return FileResponse(setup_path)
            return {"message": "Setup required. Please create initial admin."}
    except Exception:
        pass
        
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Agent API - Acesse /static/index.html"}

@app.get("/login")
async def login_page():
    """Serve a página de login (ou Setup se DB vazio)"""
    try:
        user_count = await prisma_db.db.usuario.count()
        if user_count == 0:
            ### Bug

            static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
            login_path = os.path.join(static_dir, "login.html")
            if os.path.exists(login_path):
                return FileResponse(login_path)
            return {"message": "Login page not available"}

            ## Não entendi esse redirect aqui, pois se não existe usuário ele deve ser redirecionado para um sing up por exemplo
            # from starlette.responses import RedirectResponse
            # return RedirectResponse(url="/")

    except Exception:
        pass

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    login_path = os.path.join(static_dir, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    return {"message": "Login page not available"}


class SetupRequest(BaseModel):
    admin_name: str = Field(min_length=1)
    admin_email: str = Field(min_length=5, max_length=320)
    admin_password: str = Field(min_length=8)
    group_name: str = Field(min_length=1, default="Administração")


@app.post("/api/setup")
async def setup_initial_admin(request: SetupRequest):
    """Endpoint para configuração inicial (apenas se DB vazio)"""
    user_count = await prisma_db.db.usuario.count()
    if user_count > 0:
        raise HTTPException(status_code=403, detail="Setup already completed. Users exist.")

    try:
        # Create Default Group
        grupo = await prisma_db.db.grupo.create(
            data={
                "nome": request.group_name,
                "descricao": "Grupo de administração do sistema"
            }
        )
         
        # Create Admin User
        admin_user = await prisma_db.db.usuario.create(
            data={
                "email": request.admin_email,
                "senhaHash": hash_password(request.admin_password),
                "nivel": "ADMIN_GERAL",
                "grupoId": grupo.id
            }
        )

        ## Feat: criar o token logo no singup
        ## é bom criar um service para auth

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


class LoginRequest(BaseModel):
    email: Optional[str] = None
    senha: Optional[str] = None
    token: Optional[str] = None


@app.post("/api/auth/login")
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


@app.post("/api/auth/verify")
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
            token_row = await prisma_db.db.accesstoken.find_unique(where={"jti": payload.get("jti")})
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


@app.post("/api/auth/logout")
async def logout(request: Request):
    """Endpoint de logout"""
    token = request.cookies.get("access_token")
    if token and settings.jwt_secret:
        try:
            payload = decode_access_token(token=token, secret=settings.jwt_secret, issuer=settings.jwt_issuer)
            await prisma_db.db.accesstoken.update(
                where={"jti": payload.get("jti")},
                data={"revokedAt": datetime.now(timezone.utc)},
            )
        except Exception:
            pass
    response = JSONResponse({"success": True, "message": "Logout realizado"})
    response.delete_cookie("access_token")
    return response


@app.get("/api/auth/me")
async def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _encrypt_sensitive_config(value: Any) -> Any:
    if isinstance(value, dict):
        encrypted: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).lower()
            if isinstance(v, str) and settings.encryption_key and (
                key in {"password", "senha", "secret", "token", "api_key", "apikey"} or key.endswith("_key")
            ):
                encrypted[k] = "enc:" + encrypt_str(v, settings.encryption_key)
            else:
                encrypted[k] = _encrypt_sensitive_config(v)
        return encrypted
    if isinstance(value, list):
        return [_encrypt_sensitive_config(v) for v in value]
    return value


def _pgvector_literal(values: List[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"


class GrupoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: Optional[str] = Field(default=None, max_length=500)


class GrupoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=120)
    descricao: Optional[str] = Field(default=None, max_length=500)


class UsuarioCreate(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    senha: str = Field(min_length=8, max_length=200)
    nivel: str = Field(default="NORMAL")
    grupoId: str


class UsuarioUpdate(BaseModel):
    email: Optional[str] = Field(default=None, min_length=5, max_length=320)
    senha: Optional[str] = Field(default=None, min_length=8, max_length=200)
    nivel: Optional[str] = None
    grupoId: Optional[str] = None


class AgenteCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    configuracoes: Dict[str, Any] = Field(default_factory=dict)


class AgenteUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=160)
    configuracoes: Optional[Dict[str, Any]] = None


class EmbeddingUpsert(BaseModel):
    vetor: List[float] = Field(min_length=1)


class VectorSearchRequest(BaseModel):
    vetor: List[float] = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


@app.post("/api/admin/grupos")
async def admin_create_group(request: Request, body: GrupoCreate):
    require_admin_geral(request)
    grupo = await prisma_db.db.grupo.create(data={"nome": body.nome, "descricao": body.descricao})
    return grupo


@app.get("/api/admin/grupos")
async def admin_list_groups(request: Request):
    require_admin_geral(request)
    return await prisma_db.db.grupo.find_many(order={"nome": "asc"})


@app.patch("/api/admin/grupos/{grupo_id}")
async def admin_update_group(request: Request, grupo_id: str, body: GrupoUpdate):
    require_admin_geral(request)
    data: Dict[str, Any] = {}
    if body.nome is not None:
        data["nome"] = body.nome
    if body.descricao is not None:
        data["descricao"] = body.descricao
    if not data:
        return await prisma_db.db.grupo.find_unique(where={"id": grupo_id})
    return await prisma_db.db.grupo.update(where={"id": grupo_id}, data=data)


@app.delete("/api/admin/grupos/{grupo_id}")
async def admin_delete_group(request: Request, grupo_id: str):
    require_admin_geral(request)
    await prisma_db.db.grupo.delete(where={"id": grupo_id})
    return {"deleted": True}


@app.post("/api/admin/usuarios")
async def admin_create_user(request: Request, body: UsuarioCreate):
    require_admin_geral(request)
    nivel = body.nivel
    if nivel not in {"NORMAL", "ADMIN", "ADMIN_GERAL"}:
        raise HTTPException(status_code=422, detail="Nivel inválido")
    user = await prisma_db.db.usuario.create(
        data={
            "email": body.email,
            "senhaHash": hash_password(body.senha),
            "nivel": nivel,
            "grupoId": body.grupoId,
        }
    )
    return {"id": user.id, "email": user.email, "nivel": user.nivel, "grupoId": user.grupoId}


@app.get("/api/admin/usuarios")
async def admin_list_users(request: Request, grupoId: Optional[str] = None):
    require_admin_geral(request)
    where: Dict[str, Any] = {}
    if grupoId:
        where["grupoId"] = grupoId
    users = await prisma_db.db.usuario.find_many(where=where, order={"email": "asc"})
    return [{"id": u.id, "email": u.email, "nivel": u.nivel, "grupoId": u.grupoId} for u in users]


@app.patch("/api/admin/usuarios/{usuario_id}")
async def admin_update_user(request: Request, usuario_id: str, body: UsuarioUpdate):
    require_admin_geral(request)
    data: Dict[str, Any] = {}
    if body.email is not None:
        data["email"] = body.email
    if body.senha is not None:
        data["senhaHash"] = hash_password(body.senha)
    if body.nivel is not None:
        if body.nivel not in {"NORMAL", "ADMIN", "ADMIN_GERAL"}:
            raise HTTPException(status_code=422, detail="Nivel inválido")
        data["nivel"] = body.nivel
    if body.grupoId is not None:
        data["grupoId"] = body.grupoId
    if not data:
        user = await prisma_db.db.usuario.find_unique(where={"id": usuario_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user.id, "email": user.email, "nivel": user.nivel, "grupoId": user.grupoId}
    user = await prisma_db.db.usuario.update(where={"id": usuario_id}, data=data)
    return {"id": user.id, "email": user.email, "nivel": user.nivel, "grupoId": user.grupoId}


@app.delete("/api/admin/usuarios/{usuario_id}")
async def admin_delete_user(request: Request, usuario_id: str):
    require_admin_geral(request)
    await prisma_db.db.usuario.delete(where={"id": usuario_id})
    return {"deleted": True}


@app.post("/api/grupo/agentes")
async def group_create_agent(request: Request, body: AgenteCreate):
    user = require_admin_grupo(request)
    data = {
        "nome": body.nome,
        "configuracoes": _encrypt_sensitive_config(body.configuracoes),
        "grupoId": user["grupoId"],
        "criadoPorId": user["id"],
    }
    agente = await prisma_db.db.agente.create(data=data)
    return agente


@app.get("/api/grupo/agentes")
async def group_list_agents(request: Request):
    user = get_auth(request)
    return await prisma_db.db.agente.find_many(where={"grupoId": user["grupoId"]}, order={"createdAt": "desc"})


@app.patch("/api/grupo/agentes/{agente_id}")
async def group_update_agent(request: Request, agente_id: str, body: AgenteUpdate):
    user = require_admin_grupo(request)
    agente = await prisma_db.db.agente.find_unique(where={"id": agente_id})
    if not agente or agente.grupoId != user["grupoId"]:
        raise HTTPException(status_code=404, detail="Agent not found")
    data: Dict[str, Any] = {}
    if body.nome is not None:
        data["nome"] = body.nome
    if body.configuracoes is not None:
        data["configuracoes"] = _encrypt_sensitive_config(body.configuracoes)
    if not data:
        return agente
    return await prisma_db.db.agente.update(where={"id": agente_id}, data=data)


@app.delete("/api/grupo/agentes/{agente_id}")
async def group_delete_agent(request: Request, agente_id: str):
    user = require_admin_grupo(request)
    agente = await prisma_db.db.agente.find_unique(where={"id": agente_id})
    if not agente or agente.grupoId != user["grupoId"]:
        raise HTTPException(status_code=404, detail="Agent not found")
    await prisma_db.db.agente.delete(where={"id": agente_id})
    return {"deleted": True}


@app.post("/api/grupo/agentes/{agente_id}/embedding")
async def group_set_agent_embedding(request: Request, agente_id: str, body: EmbeddingUpsert):
    user = require_admin_grupo(request)
    agente = await prisma_db.db.agente.find_unique(where={"id": agente_id})
    if not agente or agente.grupoId != user["grupoId"]:
        raise HTTPException(status_code=404, detail="Agent not found")
    await prisma_db.db.execute_raw(
        'UPDATE "Agente" SET "vetorEmbedding" = $1::vector WHERE "id" = $2::uuid',
        _pgvector_literal(body.vetor),
        agente_id,
    )
    return {"updated": True}


@app.post("/api/grupo/agentes/search")
async def group_search_agents(request: Request, body: VectorSearchRequest):
    user = get_auth(request)
    rows = await prisma_db.db.query_raw(
        'SELECT "id", "nome", "configuracoes", "grupoId", "criadoPorId", "createdAt", "updatedAt", ("vetorEmbedding" <=> $1::vector) AS score '
        'FROM "Agente" WHERE "grupoId" = $2::uuid AND "vetorEmbedding" IS NOT NULL '
        'ORDER BY "vetorEmbedding" <=> $1::vector ASC LIMIT $3',
        _pgvector_literal(body.vetor),
        user["grupoId"],
        body.top_k,
    )
    return rows


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_ok = await redis_client.ping() if redis_client else False
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "disconnected",
        "agents_loaded": len(agent_loader.list_agents()) if agent_loader else 0
    }


@app.post("/webhook/{webhook_name}")
async def webhook_entry_by_name(webhook_name: str, request: Request):
    """Endpoint de webhook usando nome personalizado"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Busca agente pelo webhook_name
    agent_config = agent_loader.get_agent_by_webhook_name(webhook_name)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_name} not found")
    
    # Redireciona para a lógica do webhook padrão
    return await webhook_entry(agent_config.id, request)


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
        
        # Sanitiza inputs
        # Sanitiza inputs com Bleach
        def sanitize_input(value):
            """Sanitiza entrada de dados usando Bleach"""
            if value is None:
                return None
            if isinstance(value, str):
                # Permite apenas tags e atributos seguros
                return bleach.clean(
                    value, 
                    tags=['b', 'i', 'u', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre'],
                    attributes={'a': ['href', 'title', 'target']},
                    strip=True
                )
            elif isinstance(value, dict):
                return {k: sanitize_input(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [sanitize_input(item) for item in value]
            return value
        
        # Sanitiza histórico se presente
        history = body.get("history", [])
        if history:
            history = sanitize_input(history)
        
        # Normaliza mensagem
        sanitized_text = sanitize_input(body.get("text", ""))
        sanitized_user_id = sanitize_input(body.get("user_id", "unknown"))
        sanitized_metadata = sanitize_input(body.get("metadata", {}))
        sanitized_conversation_id = sanitize_input(body.get("conversation_id"))
        
        message = WebhookMessage(
            user_id=sanitized_user_id,
            channel=MessageChannel(body.get("channel", "web")),
            text=sanitized_text,
            metadata=sanitized_metadata if isinstance(sanitized_metadata, dict) else {},
            conversation_id=sanitized_conversation_id
        )
        
        # Recupera histórico de mensagens (já sanitizado acima)
        
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
                        yield f"data: {json.dumps(token, ensure_ascii=False)}\n\n"
                    success = True
                except Exception as e:
                    logger.error(f"Error in stream: {e}", exc_info=True)
                    yield f"data: {json.dumps(f'[ERRO: {str(e)}]', ensure_ascii=False)}\n\n"
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
async def list_agents(request: Request):
    """Lista todos os agentes configurados (Filtrado por grupo se não for ADMIN_GERAL)"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Try to get user from request state (set by AuthMiddleware)
    user = getattr(request.state, "user", None)
    
    agents = agent_loader.list_agents()
    
    # Filter agents
    filtered_agents = []
    for agent in agents.values():
        # If user is logged in
        if user:
            # ADMIN_GERAL sees all
            if user["nivel"] == "ADMIN_GERAL":
                filtered_agents.append(agent)
            # Others see only their group's agents OR agents with no group (legacy/file-based might have no group)
            # Decisão: Agentes de arquivo (sem grupo) são visíveis para todos ou apenas Admin?
            # Por segurança, agentes sem grupo (arquivos) visíveis apenas para Admin Geral seria melhor, mas
            # para compatibilidade, vamos permitir que se 'grupoId' for None, seja visível? 
            # Melhor: Agentes do DB tem grupo. Agentes de arquivo não.
            # Vamos assumir: Se tem grupoId, deve bater. Se não tem, é público/sistema?
            # Vamos restringir: Se não tem grupoId (arquivo), mostra pra todo mundo (legacy) OU apenas admin.
            # Vamos mostrar legacy para todos por enquanto.
            elif agent.grupoId == user["grupoId"] or agent.grupoId is None:
                filtered_agents.append(agent)
        else:
             # Authentication is enforced for /agents path in middleware?
             # Middleware list: /api/* and /webhooks/* return 401. 
             # /agents is NOT /api/... 
             # Check AuthMiddleware dispatch.
             # If path is not public and not /api, it redirects to login (line 95).
             # So user SHOULD be present if browser access.
             # If accessible via API token, it returns 401.
             # So user is practically guaranteed if we reach here and it's protected.
             # Assume filtered if user is None (which shouldn't happen if protected properly)
             filtered_agents.append(agent)

    return {
        "agents": [
            {
                "id": agent.id,
                "model": agent.model,
                "has_rag": agent.rag is not None,
                "tools_count": len(agent.tools),
                "grupoId": agent.grupoId
            }
            for agent in filtered_agents
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


@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, agent: AgentConfig):
    """Atualiza um agente existente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if agent.id != agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")

    if not agent_loader.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    success = agent_loader.save_agent(agent)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update agent")

    return {"status": "updated", "agent_id": agent_id, "agent": agent.dict()}


@app.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Exclui um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    success = agent_loader.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return {"status": "deleted", "agent_id": agent_id}


@app.post("/agents/{agent_id}/reload")
async def reload_agent(agent_id: str):
    """Recarrega um agente específico"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    success = await agent_loader.reload_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Recarrega arquivos de análise de dados se houver
    agent_config = agent_loader.get_agent(agent_id)
    if agent_config and agent_config.data_analysis and agent_config.data_analysis.enabled:
        if data_analysis_service and agent_config.data_analysis.files:
            data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    return {"status": "reloaded", "agent_id": agent_id}


@app.post("/agents/reload")
async def reload_all_agents():
    """Recarrega todos os agentes"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    await agent_loader.reload()
    
    # Recarrega arquivos de análise de dados para todos os agentes
    if data_analysis_service:
        agents = agent_loader.list_agents()
        for agent_id, agent_config in agents.items():
            if agent_config.data_analysis and agent_config.data_analysis.enabled:
                if agent_config.data_analysis.files:
                    data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
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


@app.get("/rag/indexes")
async def list_rag_indexes():
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    indexes = set()
    for agent in agent_loader.list_agents().values():
        if agent.rag and getattr(agent.rag, "index_name", None):
            indexes.add(agent.rag.index_name)

    try:
        if qdrant_client and qdrant_client.client:
            for name in await qdrant_client.list_collections():
                indexes.add(name)
    except Exception:
        pass

    return {"indexes": sorted(indexes)}


@app.post("/rag/{index_name}/documents")
async def create_document(index_name: str, document: DocumentCreate, backend: str = "qdrant"):
    """Adiciona um documento ao índice RAG"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    try:
        doc_id = await rag_document_service.add_document(
            index_name=index_name,
            content=document.content,
            metadata=document.metadata,
            backend=backend,
        )
        return {"status": "created", "document_id": doc_id, "index_name": index_name}
    except Exception as e:
        logger.error(f"Error creating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/{index_name}/documents")
async def list_documents(index_name: str, limit: int = 100, backend: str = "qdrant"):
    """Lista documentos de um índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    documents = await rag_document_service.list_documents(index_name, limit, backend=backend)
    return {"index_name": index_name, "documents": documents, "count": len(documents)}


@app.delete("/rag/{index_name}/documents/{document_id}")
async def delete_document(index_name: str, document_id: str, backend: str = "qdrant"):
    """Remove um documento do índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    success = await rag_document_service.delete_document(index_name, document_id, backend=backend)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "deleted", "document_id": document_id}


@app.get("/rag/{index_name}/stats")
async def get_index_stats(index_name: str, backend: str = "qdrant"):
    """Obtém estatísticas de um índice"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    return await rag_document_service.get_index_stats(index_name, backend=backend)


@app.post("/rag/{index_name}/search")
async def search_documents(index_name: str, query: str, top_k: int = 5, backend: str = "qdrant"):
    """Busca documentos similares"""
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")
    
    results = await rag_document_service.search_documents(index_name, query, top_k, backend=backend)
    return {"index_name": index_name, "query": query, "results": results}


@app.post("/rag/{index_name}/files")
async def upload_rag_file(
    index_name: str,
    file: UploadFile = File(...),
    backend: str = Form("qdrant"),
    chunk_size: int = Form(1500),
    overlap: int = Form(300),
    metadata_json: Optional[str] = Form(None),
):
    if not rag_document_service:
        raise HTTPException(status_code=503, detail="RAG document service not initialized")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    metadata: Dict[str, Any] = {}
    if metadata_json and metadata_json.strip():
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            raise HTTPException(status_code=400, detail="metadata_json must be valid JSON")

    suffix = Path(file.filename or "").suffix or ".bin"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        text = extract_text(Path(tmp_path))
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from file")

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks generated from extracted text")

        file_hash = hashlib.sha256(raw).hexdigest()
        created_ids: List[str] = []
        for i, chunk in enumerate(chunks):
            point_hash = hashlib.sha256(f"{index_name}:{file_hash}:{i}".encode("utf-8")).hexdigest()
            doc_id = str(uuid.UUID(hex=point_hash[:32]))
            doc_metadata = {
                **metadata,
                "source_file": file.filename,
                "file_size": len(raw),
                "file_hash_sha256": file_hash,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            created_id = await rag_document_service.add_document(
                index_name=index_name,
                content=chunk,
                metadata=doc_metadata,
                document_id=doc_id,
                backend=backend,
            )
            created_ids.append(created_id)

        return {
            "status": "uploaded",
            "index_name": index_name,
            "filename": file.filename,
            "chunks": len(chunks),
            "document_ids": created_ids,
        }
    finally:
        try:
            if tmp_path:
                os.unlink(tmp_path)
        except Exception:
            pass


# ==================== DASHBOARD ====================

# ==================== AGENT CREATION ====================

class AgentCreateRequest(BaseModel):
    id: str
    nome: Optional[str] = None
    model: str = "Qwen/Qwen2.5-3B-Instruct"
    api_key: Optional[str] = None
    webhook_name: Optional[str] = None
    system_prompt: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    rag: Optional[Dict[str, Any]] = None
    data_analysis: Optional[Dict[str, Any]] = None
    tools: List[Dict[str, Any]] = Field(default_factory=list)
    webhook_output_url: Optional[str] = None


@app.post("/agents/create")
async def create_agent(request: AgentCreateRequest):
    """Cria um novo agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Verifica se agente já existe
        if agent_loader.get_agent(request.id):
            raise HTTPException(status_code=400, detail=f"Agent {request.id} already exists")
        
        # Constrói configuração RAG se fornecida
        rag_config = None
        if request.rag:
            rag_config = AgentRAGConfig(**request.rag)
        
        # Constrói configuração de análise de dados se fornecida
        data_analysis_config = None
        if request.data_analysis:
            data_analysis_config = DataAnalysisConfig(**request.data_analysis)
        
        # Constrói tools
        from app.models import AgentTool
        tools = [AgentTool(**tool) for tool in request.tools]
        
        # Cria configuração do agente
        agent_config = AgentConfig(
            id=request.id,
            nome=request.nome,
            model=request.model,
            api_key=request.api_key,
            webhook_name=request.webhook_name,
            system_prompt=request.system_prompt,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
            rag=rag_config,
            data_analysis=data_analysis_config,
            tools=tools,
            webhook_output_url=request.webhook_output_url
        )
        
        # Salva agente
        success = agent_loader.save_agent(agent_config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save agent")
        
        # Carrega arquivos de análise de dados se houver
        if data_analysis_config and data_analysis_config.enabled and data_analysis_config.files:
            data_analysis_service.load_agent_files(request.id, data_analysis_config.files)
        
        return {
            "status": "created",
            "agent_id": request.id,
            "agent": agent_config.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AGENT FILES ====================

@app.post("/agents/{agent_id}/files")
async def upload_agent_file(
    agent_id: str,
    file: UploadFile = File(...)
):
    """Upload de arquivo para um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    # Verifica se agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    try:
        # Lê conteúdo do arquivo
        content = await file.read()
        
        # Salva arquivo
        success = data_analysis_service.save_file(agent_id, file.filename, content)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to save file")
        
        # Atualiza configuração do agente se data_analysis estiver habilitado
        if agent_config.data_analysis and agent_config.data_analysis.enabled:
            if file.filename not in agent_config.data_analysis.files:
                agent_config.data_analysis.files.append(file.filename)
                agent_loader.save_agent(agent_config)
        
        return {
            "status": "uploaded",
            "filename": file.filename,
            "agent_id": agent_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/{agent_id}/files")
async def list_agent_files(agent_id: str):
    """Lista arquivos de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    # Verifica se agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    files = data_analysis_service.list_files(agent_id)
    return {
        "agent_id": agent_id,
        "files": files,
        "count": len(files)
    }


@app.delete("/agents/{agent_id}/files/{filename}")
async def delete_agent_file(agent_id: str, filename: str):
    """Remove um arquivo de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    # Verifica se agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    success = data_analysis_service.delete_file(agent_id, filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Atualiza configuração do agente
    if agent_config.data_analysis and filename in agent_config.data_analysis.files:
        agent_config.data_analysis.files.remove(filename)
        agent_loader.save_agent(agent_config)
    
    return {
        "status": "deleted",
        "filename": filename,
        "agent_id": agent_id
    }


@app.post("/agents/{agent_id}/data/query")
async def test_data_query(agent_id: str, query: str):
    """Testa uma query de dados para um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    # Verifica se agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Verifica se análise de dados está habilitada
    if not agent_config.data_analysis or not agent_config.data_analysis.enabled:
        raise HTTPException(status_code=400, detail="Data analysis not enabled for this agent")
    
    # Carrega arquivos se necessário
    if agent_config.data_analysis.files:
        data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    # Executa query
    result = data_analysis_service.execute_query(agent_id, query)
    
    return {
        "agent_id": agent_id,
        "query": query,
        "result": result
    }


@app.get("/agents/{agent_id}/data/info")
async def get_data_info(agent_id: str):
    """Obtém informações sobre os dados carregados de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    # Verifica se agente existe
    agent_config = agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Verifica se análise de dados está habilitada
    if not agent_config.data_analysis or not agent_config.data_analysis.enabled:
        raise HTTPException(status_code=400, detail="Data analysis not enabled for this agent")
    
    # Carrega arquivos se necessário
    if agent_config.data_analysis.files:
        data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    # Obtém informações
    info = data_analysis_service.get_dataframe_info(agent_id)
    
    return {
        "agent_id": agent_id,
        "info": info
    }


@app.get("/create-agent")
async def create_agent_page():
    """Serve a página de criação de agentes"""
    create_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "static",
        "create-agent.html"
    )
    if os.path.exists(create_path):
        return FileResponse(create_path)
    return {"message": "Create agent page not available"}


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


@app.get("/api/models")
async def get_models():
    """Retorna lista de modelos disponíveis"""
    modelos_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "modelos.json"
    )
    if os.path.exists(modelos_path):
        with open(modelos_path, 'r', encoding='utf-8') as f:
            modelos = json.load(f)
        return {"models": modelos}
    return {"models": []}

