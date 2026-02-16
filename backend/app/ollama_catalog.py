"""Ollama model discovery helpers (OpenClaw-style tool-capability filtering)."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOOL_MODELS_CACHE_TTL_SECONDS = 45.0
_tool_models_cache: dict[str, tuple[float, list[str]]] = {}

_OLLAMA_TOOL_MODEL_PREFERENCE_PREFIXES: tuple[str, ...] = (
    "gpt-oss",
    "llama3.3",
    "qwen2.5-coder",
    "qwen3",
    "deepseek-r1",
    "glm",
    "llama",
)


def get_ollama_base_url() -> str:
    base = (get_settings().ollama_base_url or "").strip() or "http://localhost:11434"
    return base.rstrip("/")


def _normalize_model_names(raw_names: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for raw in raw_names:
        name = str(raw or "").strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return sorted(names)


async def ollama_list_models(
    base_url: str | None = None,
    *,
    timeout: float = 3.0,
) -> list[str]:
    base = (base_url or get_ollama_base_url()).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base}/api/tags")
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("models") if isinstance(data, dict) else []
            if not isinstance(models, list):
                return []
            names: list[str] = []
            for model in models:
                if isinstance(model, dict):
                    if model.get("name"):
                        names.append(str(model.get("name") or ""))
                    elif model.get("model"):
                        names.append(str(model.get("model") or ""))
            return _normalize_model_names(names)
    except Exception:
        return []


async def ollama_model_capabilities(
    model: str,
    base_url: str | None = None,
    *,
    timeout: float = 4.0,
) -> set[str]:
    model_name = (model or "").strip()
    if not model_name:
        return set()
    base = (base_url or get_ollama_base_url()).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base}/api/show", json={"model": model_name})
            if resp.status_code != 200:
                return set()
            data = resp.json()
            caps = data.get("capabilities") if isinstance(data, dict) else None
            if not isinstance(caps, list):
                details = data.get("details") if isinstance(data, dict) else None
                caps = details.get("capabilities") if isinstance(details, dict) else None
            if not isinstance(caps, list):
                return set()
            out: set[str] = set()
            for item in caps:
                text = str(item or "").strip().lower()
                if text:
                    out.add(text)
            return out
    except Exception:
        return set()


async def ollama_model_supports_tools(
    model: str,
    base_url: str | None = None,
    *,
    timeout: float = 4.0,
) -> bool:
    caps = await ollama_model_capabilities(model, base_url=base_url, timeout=timeout)
    return "tools" in caps


async def ollama_list_tool_models(
    base_url: str | None = None,
    *,
    timeout: float = 4.0,
) -> list[str]:
    base = (base_url or get_ollama_base_url()).rstrip("/")
    now = time.monotonic()
    cached = _tool_models_cache.get(base)
    if cached and cached[0] > now:
        return list(cached[1])

    models = await ollama_list_models(base, timeout=timeout)
    if not models:
        _tool_models_cache[base] = (now + _TOOL_MODELS_CACHE_TTL_SECONDS, [])
        return []

    sem = asyncio.Semaphore(6)

    async def _check(model_name: str) -> tuple[str, bool]:
        async with sem:
            supports = await ollama_model_supports_tools(model_name, base_url=base, timeout=timeout)
            return model_name, supports

    checked = await asyncio.gather(*[_check(name) for name in models], return_exceptions=True)
    tool_models: list[str] = []
    for item in checked:
        if isinstance(item, Exception):
            logger.debug("Ollama model capability probe failed: %s", item)
            continue
        name, supports = item
        if supports:
            tool_models.append(name)
    tool_models = _normalize_model_names(tool_models)
    _tool_models_cache[base] = (now + _TOOL_MODELS_CACHE_TTL_SECONDS, tool_models)
    return tool_models


def resolve_ollama_model_name(requested: str, available_models: list[str]) -> str:
    model = (requested or "").strip()
    if not model:
        return ""
    if not available_models:
        return model
    if model in available_models:
        return model
    for candidate in available_models:
        if candidate.startswith(model + ":"):
            return candidate
    return model


def sort_ollama_models_by_preference(models: list[str]) -> list[str]:
    if not models:
        return []

    def _rank(name: str) -> tuple[int, str]:
        key = name.strip().lower()
        for idx, prefix in enumerate(_OLLAMA_TOOL_MODEL_PREFERENCE_PREFIXES):
            if key.startswith(prefix):
                return (idx, key)
        return (len(_OLLAMA_TOOL_MODEL_PREFERENCE_PREFIXES), key)

    return sorted(models, key=_rank)
