from typing import Any, Dict
from fastapi import APIRouter, Request

from app.infrastructure.database import prisma_db
from app.schemas.group import GrupoCreate, GrupoUpdate
from app.security.permissions import require_admin_geral

group_router = APIRouter(prefix="/api/admin/grupos", tags=["groups"])

@group_router.post("", operation_id="admin_create_group")
async def admin_create_group(request: Request, body: GrupoCreate):
    require_admin_geral(request)
    grupo = await prisma_db.db.grupo.create(data={"nome": body.nome, "descricao": body.descricao})
    return grupo


@group_router.get("", operation_id="admin_list_groups")
async def admin_list_groups(request: Request):
    require_admin_geral(request)
    return await prisma_db.db.grupo.find_many(order={"nome": "asc"})


@group_router.patch("/{grupo_id}", operation_id="admin_update_group")
async def admin_update_group(request: Request, grupo_id: str, body: GrupoUpdate):
    require_admin_geral(request)
    data: Dict[str, Any] = {}
    if body.nome is not None:
        data["nome"] = body.nome
    if body.descricao is not None:
        data["descricao"] = body.descricao
    if not data:
        return await prisma_db.db.grupo.find_unique(where={"id": grupo_id})
    return await prisma_db.db.grupo.update(where={"id": grupo_id}, data=data) # type: ignore


@group_router.delete("/{grupo_id}", operation_id="admin_delete_group")
async def admin_delete_group(request: Request, grupo_id: str):
    require_admin_geral(request)
    await prisma_db.db.grupo.delete(where={"id": grupo_id})
    return {"deleted": True}

