from typing import Optional
from pydantic import BaseModel, Field


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
