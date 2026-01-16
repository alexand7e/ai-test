# ==================== agents.py (PARTE 1 - Router de Grupo) ====================
from typing import Any, Dict
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.dependencies import get_container
from app.core import agent_loader
from app.core.container import Container
from app.infrastructure.database import prisma_db
from app.schemas.agent import AgentConfig, AgentCreateRequest, AgentRAGConfig, AgentTool, AgenteCreate, AgenteUpdate, DataAnalysisConfig, EmbeddingUpsert, VectorSearchRequest
from app.security.permissions import get_auth, require_admin_grupo

from app.utils.helpers import _encrypt_sensitive_config, _pgvector_literal

from app.utils.logging import logger

import json
import os

# Router para operações de grupo
grupo_agents_router = APIRouter(prefix="/api/grupo/agentes", tags=["grupo-agents"])

@grupo_agents_router.post("")
async def group_create_agent(request: Request, body: AgenteCreate):
    user = require_admin_grupo(request)
    data = {
        "nome": body.nome,
        "configuracoes": _encrypt_sensitive_config(body.configuracoes),
        "grupoId": user["grupoId"],
        "criadoPorId": user["id"],
    }
    agente = await prisma_db.db.agente.create(data=data) # type: ignore
    return agente


@grupo_agents_router.get("")
async def group_list_agents(request: Request):
    user = get_auth(request)
    return await prisma_db.db.agente.find_many(where={"grupoId": user["grupoId"]}, order={"createdAt": "desc"})


@grupo_agents_router.patch("/{agente_id}")
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
    return await prisma_db.db.agente.update(where={"id": agente_id}, data=data) # type: ignore


@grupo_agents_router.delete("/{agente_id}")
async def group_delete_agent(request: Request, agente_id: str):
    user = require_admin_grupo(request)
    agente = await prisma_db.db.agente.find_unique(where={"id": agente_id})
    if not agente or agente.grupoId != user["grupoId"]:
        raise HTTPException(status_code=404, detail="Agent not found")
    await prisma_db.db.agente.delete(where={"id": agente_id})
    return {"deleted": True}


@grupo_agents_router.post("/{agente_id}/embedding")
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


@grupo_agents_router.post("/search")
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


# ==================== agents.py (PARTE 2 - Router Principal) ====================
# Router para gestão de agentes
agents_router = APIRouter(prefix="/agents", tags=["agents"])

@agents_router.get("")
async def list_agents(request: Request, container: Container = Depends(get_container)):
    """Lista todos os agentes configurados (Filtrado por grupo)"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    user = getattr(request.state, "user", None)
    
    agents = container.agent_loader.list_agents()
    
    filtered_agents = []
    for agent in agents.values():
        if user:
            if user["nivel"] == "ADMIN_GERAL":
                filtered_agents.append(agent)
            elif agent.grupoId == user["grupoId"] or agent.grupoId is None:
                filtered_agents.append(agent)
        else:
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


@agents_router.get("/{agent_id}")
async def get_agent(agent_id: str, container: Container = Depends(get_container)):
    """Obtém detalhes de um agente"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    return agent_config.model_dump()


@agents_router.put("/{agent_id}")
async def update_agent(agent_id: str, agent: AgentConfig, container: Container = Depends(get_container)):
    """Atualiza um agente existente"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if agent.id != agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")

    if not container.agent_loader.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    success = container.agent_loader.save_agent(agent)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update agent")

    return {"status": "updated", "agent_id": agent_id, "agent": agent.model_dump()}


@agents_router.delete("/{agent_id}")
async def delete_agent(agent_id: str, container: Container = Depends(get_container)):
    """Exclui um agente"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")

    success = container.agent_loader.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    return {"status": "deleted", "agent_id": agent_id}


@agents_router.post("/{agent_id}/reload")
async def reload_agent(agent_id: str, container: Container = Depends(get_container)):
    """Recarrega um agente específico"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    success = await container.agent_loader.reload_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if agent_config and agent_config.data_analysis and agent_config.data_analysis.enabled:
        if container.data_analysis_service and agent_config.data_analysis.files:
            container.data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    return {"status": "reloaded", "agent_id": agent_id}


@agents_router.post("/reload")
async def reload_all_agents(container: Container = Depends(get_container)):
    """Recarrega todos os agentes"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    await container.agent_loader.reload()
    
    if container.data_analysis_service:
        agents = container.agent_loader.list_agents()
        for agent_id, agent_config in agents.items():
            if agent_config.data_analysis and agent_config.data_analysis.enabled:
                if agent_config.data_analysis.files:
                    container.data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    return {"status": "reloaded", "count": len(container.agent_loader.list_agents())}


@agents_router.post("/create")
async def create_agent(request: AgentCreateRequest, container: Container = Depends(get_container)):
    """Cria um novo agente"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        if container.agent_loader.get_agent(request.id):
            raise HTTPException(status_code=400, detail=f"Agent {request.id} already exists")
        
        rag_config = None
        if request.rag:
            rag_config = AgentRAGConfig(**request.rag)
        
        data_analysis_config = None
        if request.data_analysis:
            data_analysis_config = DataAnalysisConfig(**request.data_analysis)
        
        tools = [AgentTool(**tool) for tool in request.tools]
        
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
        
        success = container.agent_loader.save_agent(agent_config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save agent")
        
        if data_analysis_config and data_analysis_config.enabled and data_analysis_config.files:
            container.data_analysis_service.load_agent_files(request.id, data_analysis_config.files)
        
        return {
            "status": "created",
            "agent_id": request.id,
            "agent": agent_config.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@agents_router.post("/{agent_id}/files")
async def upload_agent_file(
    agent_id: str,
    file: UploadFile = File(...),
    container: Container = Depends(get_container)
):
    """Upload de arquivo para um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not container.data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    try:
        content = await file.read()
        
        if file.filename is None:
            raise ValueError("Filename is required")
        
        success = container.data_analysis_service.save_file(agent_id, file.filename, content)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to save file")
        
        if agent_config.data_analysis and agent_config.data_analysis.enabled:
            if file.filename not in agent_config.data_analysis.files:
                agent_config.data_analysis.files.append(file.filename)
                container.agent_loader.save_agent(agent_config)
        
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


@agents_router.get("/{agent_id}/files")
async def list_agent_files(agent_id: str, container: Container = Depends(get_container)):
    """Lista arquivos de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not container.data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    files = container.data_analysis_service.list_files(agent_id)
    return {
        "agent_id": agent_id,
        "files": files,
        "count": len(files)
    }


@agents_router.delete("/{agent_id}/files/{filename}")
async def delete_agent_file(agent_id: str, filename: str, container: Container = Depends(get_container)):
    """Remove um arquivo de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not container.data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    success = container.data_analysis_service.delete_file(agent_id, filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    
    if agent_config.data_analysis and filename in agent_config.data_analysis.files:
        agent_config.data_analysis.files.remove(filename)
        container.agent_loader.save_agent(agent_config)
    
    return {
        "status": "deleted",
        "filename": filename,
        "agent_id": agent_id
    }


@agents_router.post("/{agent_id}/data/query")
async def test_data_query(agent_id: str, query: str, container: Container = Depends(get_container)):
    """Testa uma query de dados para um agente"""
    if not container.agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not container.data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    if not agent_config.data_analysis or not agent_config.data_analysis.enabled:
        raise HTTPException(status_code=400, detail="Data analysis not enabled for this agent")
    
    if agent_config.data_analysis.files:
        container.data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    result = container.data_analysis_service.execute_query(agent_id, query)
    
    return {
        "agent_id": agent_id,
        "query": query,
        "result": result
    }


@agents_router.get("/{agent_id}/data/info")
async def get_data_info(agent_id: str, container: Container = Depends(get_container)):
    """Obtém informações sobre os dados carregados de um agente"""
    if not agent_loader:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    if not container.data_analysis_service:
        raise HTTPException(status_code=503, detail="Data analysis service not initialized")
    
    agent_config = container.agent_loader.get_agent(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    if not agent_config.data_analysis or not agent_config.data_analysis.enabled:
        raise HTTPException(status_code=400, detail="Data analysis not enabled for this agent")
    
    if agent_config.data_analysis.files:
        container.data_analysis_service.load_agent_files(agent_id, agent_config.data_analysis.files)
    
    info = container.data_analysis_service.get_dataframe_info(agent_id)
    
    return {
        "agent_id": agent_id,
        "info": info
    }

@agents_router.get("/api/models")
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
