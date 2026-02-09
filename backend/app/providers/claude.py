"""Claude (Anthropic) provider (key from panel Settings or .env)."""
from anthropic import AsyncAnthropic
from app.providers.base import BaseProvider, Message
from app.keys import get_api_key


class ClaudeProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "claude"

    async def chat(self, messages: list[Message], **kwargs) -> str:
        key = await get_api_key("anthropic_api_key")
        if not key:
            return "Error: Anthropic API key not set. Add it in Settings (API keys) or in backend/.env as ANTHROPIC_API_KEY."
        client = AsyncAnthropic(api_key=key)
        system = kwargs.get("context", "")
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        model = kwargs.get("model") or "claude-3-5-sonnet-20241022"
        r = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system or None,
            messages=msgs,
        )
        return (r.content[0].text if r.content else "").strip()
