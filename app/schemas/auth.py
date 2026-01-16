from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: Optional[str] = None
    senha: Optional[str] = None
    token: Optional[str] = None

class SetupRequest(BaseModel):
    admin_name: str = Field(min_length=1)
    admin_email: str = Field(min_length=5, max_length=320)
    admin_password: str = Field(min_length=8)
    group_name: str = Field(min_length=1, default="Administração")
