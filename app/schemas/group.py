from typing import Optional
from pydantic import BaseModel, Field

class GrupoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: Optional[str] = Field(default=None, max_length=500)


class GrupoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=120)
    descricao: Optional[str] = Field(default=None, max_length=500)

