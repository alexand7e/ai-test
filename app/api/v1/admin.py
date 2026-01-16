from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request

from app.infrastructure.database import prisma_db
from app.schemas.user import UsuarioCreate, UsuarioUpdate
from app.security.passwords import hash_password
from app.security.permissions import require_admin_geral

from app.schemas.group import GrupoCreate, GrupoUpdate

admin_router = APIRouter(prefix="/api/admin", tags=["administration"])

@admin_router.post("/grupos")
async def admin_create_group(request: Request, body: GrupoCreate):
    require_admin_geral(request)
    grupo = await prisma_db.db.grupo.create(data={"nome": body.nome, "descricao": body.descricao})
    return grupo


@admin_router.get("/grupos")
async def admin_list_groups(request: Request):
    require_admin_geral(request)
    return await prisma_db.db.grupo.find_many(order={"nome": "asc"})


@admin_router.patch("/grupos/{grupo_id}")
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


@admin_router.delete("/grupos/{grupo_id}")
async def admin_delete_group(request: Request, grupo_id: str):
    require_admin_geral(request)
    await prisma_db.db.grupo.delete(where={"id": grupo_id})
    return {"deleted": True}


@admin_router.post("/usuarios")
async def admin_create_user(request: Request, body: UsuarioCreate):
    require_admin_geral(request)
    nivel = body.nivel
    if nivel not in {"NORMAL", "ADMIN", "ADMIN_GERAL"}:
        raise HTTPException(status_code=422, detail="Nivel inválido")
    user = await prisma_db.db.usuario.create(
        data={
            "email": body.email,
            "senhaHash": hash_password(body.senha),
            "nivel": nivel, # type: ignore
            "grupoId": body.grupoId,
        }
    )
    return {"id": user.id, "email": user.email, "nivel": user.nivel, "grupoId": user.grupoId}


@admin_router.get("/usuarios")
async def admin_list_users(request: Request, grupoId: Optional[str] = None):
    require_admin_geral(request)
    where: Dict[str, Any] = {}
    if grupoId:
        where["grupoId"] = grupoId
    users = await prisma_db.db.usuario.find_many(where=where, order={"email": "asc"}) # type: ignore
    return [{"id": u.id, "email": u.email, "nivel": u.nivel, "grupoId": u.grupoId} for u in users]


@admin_router.patch("/usuarios/{usuario_id}")
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
    user = await prisma_db.db.usuario.update(where={"id": usuario_id}, data=data) # type: ignore
    return {"id": user.id, "email": user.email, "nivel": user.nivel, "grupoId": user.grupoId} # type: ignore


@admin_router.delete("/usuarios/{usuario_id}")
async def admin_delete_user(request: Request, usuario_id: str):
    require_admin_geral(request)
    await prisma_db.db.usuario.delete(where={"id": usuario_id})
    return {"deleted": True}
