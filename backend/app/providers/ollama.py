"""Ollama provider (local) using native /api/chat with OpenClaw-style tool support."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

import httpx

from app.ollama_catalog import (
    get_ollama_base_url,
    ollama_list_models,
    ollama_list_tool_models,
    ollama_model_supports_tools,
    resolve_ollama_model_name,
    sort_ollama_models_by_preference,
)
from app.providers.base import (
    BaseProvider,
    Message,
    ProviderError,
    ProviderResponse,
    TextDeltaCallback,
    emit_text_delta,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 120.0
_STREAM_TIMEOUT_SECONDS = 180.0


def _parse_model_candidates(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for chunk in str(raw).split(","):
        model = chunk.strip()
        if not model:
            continue
        key = model.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(model)
    return out


def _parse_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _to_ollama_tools(tools: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for t in (tools or []):
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(fn.get("description") or ""),
                    "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def _to_ollama_messages(
    messages: list[Message],
    system_prompt: str | None = None,
    image_b64: str | None = None,
) -> list[dict]:
    out: list[dict] = []
    tool_name_by_id: dict[str, str] = {}

    if system_prompt:
        out.append({"role": "system", "content": system_prompt})

    for m in messages:
        role = str(m.get("role") or "").strip().lower()
        content = str(m.get("content") or "")
        if role == "assistant" and m.get("tool_calls"):
            tc_items: list[dict] = []
            for tc in (m.get("tool_calls") or []):
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                name = str(fn.get("name") or "").strip()
                if not name:
                    continue
                args_obj = _parse_tool_args(fn.get("arguments"))
                tc_items.append(
                    {
                        "type": "function",
                        "function": {"name": name, "arguments": args_obj},
                    }
                )
                tc_id = str(tc.get("id") or "").strip()
                if tc_id:
                    tool_name_by_id[tc_id] = name
            msg: dict[str, Any] = {"role": "assistant", "content": content}
            if tc_items:
                msg["tool_calls"] = tc_items
            out.append(msg)
            continue

        if role == "tool":
            msg = {"role": "tool", "content": content}
            tool_call_id = str(m.get("tool_call_id") or "").strip()
            tool_name = tool_name_by_id.get(tool_call_id)
            if tool_name:
                msg["tool_name"] = tool_name
            out.append(msg)
            continue

        msg_role = "assistant" if role == "assistant" else "user"
        msg: dict[str, Any] = {"role": msg_role, "content": content}
        if msg_role == "user" and image_b64 and m == messages[-1]:
            msg["images"] = [image_b64]
        out.append(msg)

    return out


def _from_ollama_tool_calls(raw_tool_calls: list[Any] | None) -> list[dict] | None:
    if not raw_tool_calls:
        return None
    out: list[dict] = []
    for idx, tc in enumerate(raw_tool_calls):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        args = fn.get("arguments")
        try:
            args_str = json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False)
        except Exception:
            args_str = "{}"
        out.append(
            {
                "id": f"ollama_tool_{idx}_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            }
        )
    return out or None


# Models that should be automatically pulled if not available
_AUTO_PULL_MODELS: tuple[str, ...] = (
    "minimax-m2.5:cloud",
)


async def _ensure_model_pulled(model: str, base_url: str) -> None:
    """Ensure a model is pulled in Ollama. Skip for cloud models as they're remote."""
    # Cloud models (ending with :cloud) don't need pulling - they're accessed remotely
    if model.endswith(":cloud"):
        return

    installed = await ollama_list_models(base_url=base_url)
    if model in installed:
        return

    # Try to pull the model
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            await client.post(f"{base_url}/api/pull", json={"model": model})
            logger.info(f"Pulled Ollama model: {model}")
    except Exception as e:
        logger.warning(f"Failed to pull Ollama model {model}: {e}")


async def _resolve_models_for_request(
    *,
    model_raw: str | None,
    need_tools: bool,
    base_url: str,
) -> tuple[list[str], str | None]:
    # Check if we need to pull any models proactively
    for model in _AUTO_PULL_MODELS:
        await _ensure_model_pulled(model, base_url)

    installed = await ollama_list_models(base_url=base_url)
    explicit = _parse_model_candidates(model_raw)
    if explicit:
        resolved: list[str] = [resolve_ollama_model_name(m, installed) for m in explicit]
        if not need_tools:
            return resolved, None
        allowed: list[str] = []
        skipped: list[str] = []
        for model in resolved:
            if await ollama_model_supports_tools(model, base_url=base_url):
                allowed.append(model)
            else:
                skipped.append(model)
        if allowed:
            return allowed, None
        skipped_text = ", ".join(skipped) if skipped else ", ".join(resolved)
        return (
            [],
            (
                "Configured Ollama model is not tool-capable for this task. "
                f"Checked: {skipped_text}. "
                "Use a tool-capable model (e.g. gpt-oss:20b, llama3.3, qwen2.5-coder:32b)."
            ),
        )

    if need_tools:
        tool_models = await ollama_list_tool_models(base_url=base_url)
        if tool_models:
            return sort_ollama_models_by_preference(tool_models), None
        return (
            [],
            (
                "No tool-capable Ollama models detected. Pull one with tools support "
                "(e.g. gpt-oss:20b, llama3.3, qwen2.5-coder:32b), then retry."
            ),
        )

    if installed:
        return sort_ollama_models_by_preference(installed), None
    return ["llama3.2"], None


class OllamaProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "ollama"

    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        # Thinking injection: Kimi/Moonshot on Ollama requires strict system prompt to emit tokens.
        thinking_level = kwargs.get("thinking_level")
        if thinking_level and str(thinking_level).lower() not in ("off", "0", "false"):
            think_instruction = (
                "You are a deep thinking AI. "
                "Always output your step-by-step reasoning process enclosed in <think> tags "
                "before your final response."
            )
            # Add to context (system prompt)
            ctx = kwargs.get("context") or ""
            if think_instruction not in ctx:
                kwargs["context"] = f"{ctx}\n\n{think_instruction}".strip()

            # Compatibility path: some local reasoning models behave better with an explicit
            # inline `/think <level>` directive on the final user turn.
            injected_messages = [dict(m) for m in messages]
            normalized_level = str(thinking_level).strip().lower()
            for idx in range(len(injected_messages) - 1, -1, -1):
                msg = injected_messages[idx]
                if str(msg.get("role") or "").strip().lower() != "user":
                    continue
                content = str(msg.get("content") or "")
                if content.strip().lower().startswith("/think"):
                    break
                msg["content"] = f"/think {normalized_level}\n\n{content}".strip()
                break
            messages = injected_messages

        base = get_ollama_base_url()
        tools = kwargs.get("tools")
        need_tools = bool(tools)
        system_prompt = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_b64 = base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
        ollama_messages = _to_ollama_messages(messages, system_prompt=system_prompt, image_b64=image_b64)
        ollama_tools = _to_ollama_tools(tools)
        models, model_error = await _resolve_models_for_request(
            model_raw=kwargs.get("model"),
            need_tools=need_tools,
            base_url=base,
        )
        if model_error:
            return ProviderResponse(
                content="",
                error=ProviderError.MODEL_NOT_FOUND,
                error_message=model_error,
            )

        last_error = ""
        for idx, model in enumerate(models):
            payload: dict[str, Any] = {
                "model": model,
                "stream": False,
                "messages": ollama_messages,
            }
            if ollama_tools:
                payload["tools"] = ollama_tools
            
            # Enable thinking for Qwen2.5/3 models
            if "qwen" in model.lower():
                payload["thinking"] = {"type": "enabled"}

            try:
                async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                    resp = await client.post(f"{base}/api/chat", json=payload)
                if resp.status_code >= 400:
                    msg = resp.text[:500]
                    last_error = f"Ollama model '{model}' failed: {msg}"
                    if idx < len(models) - 1:
                        logger.warning("%s, trying fallback %s", last_error, models[idx + 1])
                        continue
                    break
                data = resp.json() if resp.content else {}
                message = data.get("message") if isinstance(data, dict) else {}
                # Extract thinking field and convert to XML tags (like OpenRouter does)
                thinking = str((message or {}).get("thinking") or "")
                content = str((message or {}).get("content") or "").strip()
                # Prepend thinking with XML tags if present
                if thinking:
                    content = f"<think>{thinking}</think>\n{content}"
                tool_calls = _from_ollama_tool_calls((message or {}).get("tool_calls"))
                return ProviderResponse(content=content, tool_calls=tool_calls)
            except Exception as e:
                last_error = f"Ollama model '{model}' error: {e}"
                if idx < len(models) - 1:
                    logger.warning("%s, trying fallback %s", last_error, models[idx + 1])
                    continue
                break

        low = last_error.lower()
        if "not found" in low or "model" in low and "unknown" in low:
            return ProviderResponse(
                content="",
                error=ProviderError.MODEL_NOT_FOUND,
                error_message=last_error or "Ollama model not found.",
            )
        return ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=last_error or "Ollama error",
        )

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        on_text_delta: TextDeltaCallback | None = None,
        **kwargs,
    ) -> ProviderResponse:
        # Thinking injection: Kimi/Moonshot on Ollama requires strict system prompt to emit tokens.
        thinking_level = kwargs.get("thinking_level")
        if thinking_level and str(thinking_level).lower() not in ("off", "0", "false"):
            think_instruction = (
                "You are a deep thinking AI. "
                "Always output your step-by-step reasoning process enclosed in <think> tags "
                "before your final response."
            )
            # Add to context (system prompt)
            ctx = kwargs.get("context") or ""
            if think_instruction not in ctx:
                kwargs["context"] = f"{ctx}\n\n{think_instruction}".strip()

        base = get_ollama_base_url()
        tools = kwargs.get("tools")
        need_tools = bool(tools)
        system_prompt = kwargs.get("context", "")
        image_bytes: bytes | None = kwargs.get("image_bytes")
        image_b64 = base64.b64encode(image_bytes).decode("utf-8") if image_bytes else None
        ollama_messages = _to_ollama_messages(messages, system_prompt=system_prompt, image_b64=image_b64)
        ollama_tools = _to_ollama_tools(tools)
        models, model_error = await _resolve_models_for_request(
            model_raw=kwargs.get("model"),
            need_tools=need_tools,
            base_url=base,
        )
        if model_error:
            return ProviderResponse(
                content="",
                error=ProviderError.MODEL_NOT_FOUND,
                error_message=model_error,
            )

        last_error = ""
        for idx, model in enumerate(models):
            payload: dict[str, Any] = {
                "model": model,
                "stream": True,
                "messages": ollama_messages,
            }
            if ollama_tools:
                payload["tools"] = ollama_tools
            
            # Enable thinking for Qwen2.5/3 models
            if "qwen" in model.lower():
                payload["thinking"] = {"type": "enabled"}
            
            content_parts: list[str] = []
            raw_tool_calls: list[Any] = []
            # Track if we're in a thinking block for streaming
            is_thinking = False
            try:
                async with httpx.AsyncClient(timeout=_STREAM_TIMEOUT_SECONDS) as client:
                    async with client.stream("POST", f"{base}/api/chat", json=payload) as resp:
                        if resp.status_code >= 400:
                            msg = (await resp.aread()).decode("utf-8", errors="ignore")[:500]
                            raise RuntimeError(f"Ollama model '{model}' failed: {msg}")
                        async for line in resp.aiter_lines():
                            line = (line or "").strip()
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                            except Exception:
                                logger.debug("Skipping malformed Ollama stream line: %s", line[:120])
                                continue
                            msg = chunk.get("message") if isinstance(chunk, dict) else {}
                            
                            # Extract thinking delta for streaming (like OpenRouter does)
                            thinking_delta = str((msg or {}).get("thinking") or "")
                            if thinking_delta:
                                if not is_thinking:
                                    # Start thinking block
                                    content_parts.append("<think>")
                                    await emit_text_delta(on_text_delta, "<think>")
                                    is_thinking = True
                                content_parts.append(thinking_delta)
                                await emit_text_delta(on_text_delta, thinking_delta)
                            
                            delta = str((msg or {}).get("content") or "")
                            if delta:
                                if is_thinking:
                                    # Close thinking block before content
                                    content_parts.append("</think>")
                                    await emit_text_delta(on_text_delta, "</think>")
                                    is_thinking = False
                                content_parts.append(delta)
                                await emit_text_delta(on_text_delta, delta)
                            
                            tc = (msg or {}).get("tool_calls")
                            if isinstance(tc, list):
                                raw_tool_calls.extend(tc)
                            if chunk.get("done"):
                                break
                
                # Close thinking tag if stream ended while thinking
                if is_thinking:
                    content_parts.append("</think>")
                    if on_text_delta:
                        await emit_text_delta(on_text_delta, "</think>")
                
                return ProviderResponse(
                    content="".join(content_parts).strip(),
                    tool_calls=_from_ollama_tool_calls(raw_tool_calls),
                )
            except Exception as e:
                last_error = f"Ollama model '{model}' error: {e}"
                if idx < len(models) - 1:
                    logger.warning("%s, trying fallback %s", last_error, models[idx + 1])
                    continue
                break

        low = last_error.lower()
        if "not found" in low or "model" in low and "unknown" in low:
            return ProviderResponse(
                content="",
                error=ProviderError.MODEL_NOT_FOUND,
                error_message=last_error or "Ollama model not found.",
            )
        return ProviderResponse(
            content="",
            error=ProviderError.TRANSIENT,
            error_message=last_error or "Ollama error",
        )
