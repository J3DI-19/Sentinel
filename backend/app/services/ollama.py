import httpx

from app.core.config import Settings


async def ollama_status(settings: Settings) -> dict[str, object]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {model.get("name") for model in models if isinstance(model, dict)}
            return {
                "available": True,
                "model": settings.ollama_model,
                "model_installed": settings.ollama_model in names,
            }
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            "available": False,
            "model": settings.ollama_model,
            "model_installed": False,
        }

