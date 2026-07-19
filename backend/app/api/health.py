from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.services.ollama import ollama_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/health/db")
async def database_health(request: Request) -> dict[str, object]:
    repository = request.app.state.repository
    return {"status": "ok" if repository.is_available() else "unavailable", "service": "database"}


@router.get("/health/ai")
async def ai_health() -> dict[str, object]:
    return {"service": "ollama", **await ollama_status(get_settings())}

