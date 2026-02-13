"""Ollama provider (local)."""
import httpx
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.config import get_settings


class OllamaProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "ollama"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        settings = get_settings()
        base = settings.ollama_base_url.rstrip("/")
        model = kwargs.get("model") or "llama3.2"
        system = kwargs.get("context", "")
        payload = {"model": model, "stream": False}
        if system:
            payload["messages"] = [{"role": "system", "content": system}] + [
                {"role": m["role"], "content": m["content"]} for m in messages
            ]
        else:
            payload["messages"] = [{"role": m["role"], "content": m["content"]} for m in messages]
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(f"{base}/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
            return ProviderResponse(content=(data.get("message") or {}).get("content", ""))
        except Exception as e:
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Ollama error: {e}"
            )
