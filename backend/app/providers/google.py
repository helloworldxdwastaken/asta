"""Google Gemini provider (key from panel Settings or .env)."""
import json
import re

import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.keys import get_api_key


class GoogleProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "google"

    @staticmethod
    def _tool_names(openai_tools: list[dict] | None) -> set[str]:
        names: set[str] = set()
        for t in (openai_tools or []):
            fn = t.get("function") if isinstance(t, dict) else None
            if isinstance(fn, dict):
                name = (fn.get("name") or "").strip()
                if name:
                    names.add(name)
        return names

    @staticmethod
    def _extract_tool_call_from_text(text: str, allowed_names: set[str]) -> tuple[list[dict] | None, str]:
        m = re.search(r"\[ASTA_TOOL_CALL\]\s*(\{.*?\})\s*\[/ASTA_TOOL_CALL\]", text, re.DOTALL)
        if not m:
            return None, text
        payload_raw = m.group(1).strip()
        try:
            payload = json.loads(payload_raw)
        except Exception:
            return None, text
        if not isinstance(payload, dict):
            return None, text
        name = str(payload.get("name") or "").strip()
        if not name or (allowed_names and name not in allowed_names):
            return None, text
        args = payload.get("arguments")
        if not isinstance(args, dict):
            args = {}
        tool_calls = [
            {
                "id": "google_tool_call",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
            }
        ]
        cleaned = (text[: m.start()] + text[m.end() :]).strip()
        return tool_calls, cleaned

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        key = await get_api_key("gemini_api_key") or await get_api_key("google_ai_key")
        if not key:
            return ProviderResponse(
                content="",
                error=ProviderError.AUTH,
                error_message="Google/Gemini API key not set. Add it in Settings (API keys) or in backend/.env as GEMINI_API_KEY or GOOGLE_AI_KEY."
            )
        genai.configure(api_key=key)
        model = genai.GenerativeModel(kwargs.get("model") or "gemini-1.5-flash")
        system = kwargs.get("context", "")
        tools = kwargs.get("tools")
        allowed_tool_names = self._tool_names(tools)

        parts = []
        if system:
            parts.append(system + "\n\n")
        if tools:
            parts.append(
                "TOOL-CALL PROTOCOL:\n"
                "If you need a tool, output exactly one tag in this format and nothing else:\n"
                "[ASTA_TOOL_CALL]{\"name\":\"tool_name\",\"arguments\":{...}}[/ASTA_TOOL_CALL]\n"
                f"Allowed tool names: {', '.join(sorted(allowed_tool_names))}\n\n"
            )
        for m in messages:
            role = (m.get("role") or "").strip()
            content = m.get("content") or ""
            if role == "assistant" and m.get("tool_calls"):
                parts.append(f"assistant: {content}\n")
                try:
                    parts.append(f"assistant_tool_calls: {json.dumps(m.get('tool_calls') or [], ensure_ascii=False)}\n")
                except Exception:
                    parts.append("assistant_tool_calls: []\n")
                continue
            if role == "tool":
                parts.append(f"tool_result[{m.get('tool_call_id') or ''}]: {content}\n")
                continue
            parts.append(f"{role}: {content}\n")
        prompt = "".join(parts) + "assistant:"
        try:
            r = await model.generate_content_async(prompt)
            content = (r.text or "").strip()
            if tools:
                tool_calls, cleaned = self._extract_tool_call_from_text(content, allowed_tool_names)
                if tool_calls:
                    return ProviderResponse(content=cleaned, tool_calls=tool_calls)
            return ProviderResponse(content=content)
        except Exception as e:
            msg = str(e)
            if "API key not valid" in msg or "401" in msg:
                 return ProviderResponse(
                    content="",
                    error=ProviderError.AUTH,
                    error_message=f"Google API key invalid: {msg}"
                )
            if "429" in msg or "Resource has been exhausted" in msg:
                 return ProviderResponse(
                    content="",
                    error=ProviderError.RATE_LIMIT,
                    error_message=f"Google rate limit: {msg}"
                )
            return ProviderResponse(
                content="",
                error=ProviderError.TRANSIENT,
                error_message=f"Google API error: {msg}"
            )
