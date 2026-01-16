from app.core.container import Container
from fastapi import Request

def get_container(request: Request) -> Container:
    """Dependency para obter container"""
    return request.app.state.container
