"""Claude (Anthropic) provider (key from panel Settings or .env)."""
from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key


class ClaudeProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "claude"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("anthropic_api_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Anthropic API key not set. Add it in Settings (API keys) or in backend/.env as ANTHROPIC_API_KEY."
            )
        client = AsyncAnthropic(api_key=key)
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        try:
            r = await client.messages.create(
                model=model,
                max_tokens=1024,
                system=system or None,
                messages=msgs,
            )
            return ProviderResponse(content=(r.content[0].text if r.content else "").strip())
        except Exception as e:
            msg = str(e)
            if "authentication" in msg.lower() or "401" in msg:
                return ProviderResponse(
                    content="", 
                    error=ProviderError.AUTH, 
                    error_message=f"Anthropic API key invalid: {msg}"
                )
            if "rate limit" in msg.lower() or "429" in msg:
                return ProviderResponse(
                    content="", 
                    error=ProviderError.RATE_LIMIT, 
                    error_message=f"Anthropic rate limit: {msg}"
                )
            if "not found" in msg.lower() or "404" in msg:
                 return ProviderResponse(
                    content="", 
                    error=ProviderError.MODEL_NOT_FOUND, 
                    error_message=f"Anthropic model {model} not found: {msg}"
                )
            return ProviderResponse(
                content="", 
                error=ProviderError.TRANSIENT,
                error_message=f"Anthropic error: {msg}"
            )
