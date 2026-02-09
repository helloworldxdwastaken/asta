"""List available AI providers."""
from fastapi import APIRouter
from app.providers.registry import list_providers

router = APIRouter()


@router.get("/providers")
async def get_providers():
    return {"providers": list_providers()}
