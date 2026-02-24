"""Image generation tool — Gemini primary, Hugging Face FLUX.1-dev fallback."""
import asyncio
import base64
import io
import json
import logging
import time
from collections import deque
from typing import Any

import httpx
from huggingface_hub import HfApi, InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.keys import get_api_key

logger = logging.getLogger(__name__)

# Gemini: ~10 RPM free tier
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Hugging Face Inference Providers: FLUX.1-dev (requires HF token/credits).
HUGGINGFACE_IMAGE_MODEL = "black-forest-labs/FLUX.1-dev"
HUGGINGFACE_PROVIDER_PRIORITY: tuple[str, ...] = (
    "auto",
    "fal-ai",
    "nscale",
    "nebius",
    "replicate",
    "together",
    "black-forest-labs",
    "hf-inference",
)
HUGGINGFACE_MAX_PROVIDER_ATTEMPTS = 4
HUGGINGFACE_MAX_REQUESTS_PER_MINUTE = 5
_HF_WINDOW_SECONDS = 60.0
_hf_rate_lock = asyncio.Lock()
_hf_request_timestamps: deque[float] = deque()
_HF_PROVIDER_CACHE_TTL_SECONDS = 300.0
_hf_provider_cache_lock = asyncio.Lock()
_hf_provider_cache: dict[str, tuple[float, tuple[str, ...]]] = {}


def get_image_gen_tool_openai_def() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "image_gen",
                "description": (
                    "Generate an image from a text prompt. "
                    "Use when the user asks you to create, draw, generate, make, or visualize an image. "
                    "Returns an inline image the user can see immediately."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Detailed description of the image to generate. Be specific about style, colors, composition.",
                        }
                    },
                    "required": ["prompt"],
                },
            },
        }
    ]


async def _run_gemini(key: str, prompt: str) -> str | None:
    """Try Gemini image gen. Returns JSON result string, or None on rate limit."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{GEMINI_API_BASE}/models/{GEMINI_IMAGE_MODEL}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
                },
            )
            r.raise_for_status()
            data = r.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return json.dumps({"error": "No candidates in Gemini response"})

        parts = (candidates[0].get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData")
            if inline:
                b64 = inline.get("data", "")
                mime = inline.get("mimeType", "image/png")
                return json.dumps({
                    "ok": True,
                    "image_markdown": f"![{prompt[:60]}](data:{mime};base64,{b64})",
                    "prompt": prompt,
                    "provider": "gemini",
                })

        for part in parts:
            if "text" in part:
                return json.dumps({"error": f"Image blocked or not generated: {part['text']}"})

        return json.dumps({"error": "No image returned from Gemini"})

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status == 429:
            logger.warning("Gemini image gen rate limited, falling back to Hugging Face")
            return None  # Signal to try fallback
        if status in (401, 403):
            return json.dumps({"error": f"Google API key invalid or unauthorized ({status})"})
        body = e.response.text[:300]
        return json.dumps({"error": f"Gemini image gen error {status}: {body}"})
    except Exception as e:
        logger.warning("Gemini image gen exception: %s", e)
        return None  # Try fallback on any failure


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = (value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _discover_hf_live_providers_sync(model: str, token: str) -> tuple[str, ...]:
    api = HfApi(token=token)
    info = api.model_info(model, expand=["inferenceProviderMapping"])
    mappings: Any = getattr(info, "inference_provider_mapping", None) or []
    providers: list[str] = []
    for row in mappings:
        provider = getattr(row, "provider", None)
        status = getattr(row, "status", None)
        if isinstance(row, dict):
            provider = provider or row.get("provider")
            status = status or row.get("status")
        if not provider:
            continue
        normalized_status = str(status or "").strip().lower()
        if normalized_status and normalized_status not in {"live", "staging"}:
            continue
        providers.append(str(provider))
    return tuple(_dedupe_keep_order(providers))


async def _get_hf_provider_attempt_order(model: str, token: str) -> list[str]:
    now = time.monotonic()
    cached: tuple[float, tuple[str, ...]] | None = None
    async with _hf_provider_cache_lock:
        cached = _hf_provider_cache.get(model)
    if cached and (now - cached[0]) < _HF_PROVIDER_CACHE_TTL_SECONDS:
        discovered = list(cached[1])
    else:
        discovered = []
        try:
            discovered = list(await asyncio.to_thread(_discover_hf_live_providers_sync, model, token))
        except Exception as e:
            logger.warning("HF provider discovery failed for model=%s: %s", model, e)
        async with _hf_provider_cache_lock:
            _hf_provider_cache[model] = (time.monotonic(), tuple(discovered))

    ordered = _dedupe_keep_order(["auto", *discovered, *list(HUGGINGFACE_PROVIDER_PRIORITY)])
    return ordered[: max(1, int(HUGGINGFACE_MAX_PROVIDER_ATTEMPTS))]


def _hf_error_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status_code", None)
    if status is None:
        return None
    try:
        return int(status)
    except Exception:
        return None


def _hf_error_detail(exc: Exception) -> str:
    return " ".join(str(exc).split())[:300]


async def _acquire_hf_rate_slot(max_requests_per_minute: int = HUGGINGFACE_MAX_REQUESTS_PER_MINUTE) -> None:
    """Global in-process throttle: never exceed N Hugging Face requests per minute."""
    capacity = max(1, int(max_requests_per_minute))
    while True:
        wait_for = 0.0
        async with _hf_rate_lock:
            now = time.monotonic()
            while _hf_request_timestamps and (now - _hf_request_timestamps[0]) >= _HF_WINDOW_SECONDS:
                _hf_request_timestamps.popleft()
            if len(_hf_request_timestamps) < capacity:
                _hf_request_timestamps.append(now)
                return
            wait_for = _HF_WINDOW_SECONDS - (now - _hf_request_timestamps[0]) + 0.01
        await asyncio.sleep(max(0.01, wait_for))


def _hf_generate_image_sync(key: str, prompt: str, model: str, provider: str) -> tuple[bytes, str]:
    client = InferenceClient(provider=provider, api_key=key, timeout=120.0)
    image = client.text_to_image(prompt, model=model)
    if image is None:
        raise RuntimeError("Hugging Face returned no image payload")

    if isinstance(image, (bytes, bytearray)):
        return bytes(image), "image/png"

    save = getattr(image, "save", None)
    if not callable(save):
        raise RuntimeError(f"Unsupported image return type from Hugging Face: {type(image)!r}")

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


async def _hf_generate_image(key: str, prompt: str, model: str, provider: str) -> tuple[bytes, str]:
    return await asyncio.to_thread(_hf_generate_image_sync, key, prompt, model, provider)


async def _run_huggingface(key: str, prompt: str) -> str:
    """Hugging Face FLUX.1-dev fallback. Requires API token."""
    model = HUGGINGFACE_IMAGE_MODEL
    providers = await _get_hf_provider_attempt_order(model, key)
    last_error = "Hugging Face request failed"

    for provider in providers:
        try:
            await _acquire_hf_rate_slot()
            image_bytes, mime = await _hf_generate_image(key, prompt, model, provider)
            if not image_bytes:
                last_error = f"provider={provider} returned empty image bytes"
                logger.warning("HF image gen returned empty image bytes model=%s provider=%s", model, provider)
                continue
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            return json.dumps(
                {
                    "ok": True,
                    "image_markdown": f"![{prompt[:60]}](data:{mime};base64,{b64})",
                    "prompt": prompt,
                    "provider": "huggingface",
                    "model": model,
                    "hf_provider": provider,
                }
            )
        except InferenceTimeoutError as e:
            last_error = _hf_error_detail(e)
            logger.warning("HF image gen timeout model=%s provider=%s detail=%s", model, provider, last_error)
            continue
        except HfHubHTTPError as e:
            status = _hf_error_status(e)
            detail = _hf_error_detail(e)
            if status in (401, 403):
                return json.dumps(
                    {
                        "error": (
                            f"Hugging Face API key invalid or unauthorized ({status}). "
                            "Set a valid token in Settings → API keys."
                        )
                    }
                )
            if status == 402:
                return json.dumps(
                    {
                        "error": (
                            "Hugging Face credits exhausted (402). "
                            "Top up credits or switch provider."
                        )
                    }
                )
            if status == 429:
                return json.dumps({"error": "Hugging Face rate limit reached (429). Try again shortly."})

            last_error = detail or f"HTTP {status or 'n/a'}"
            logger.warning(
                "HF image gen error model=%s provider=%s status=%s detail=%s",
                model,
                provider,
                status,
                detail,
            )
            if status in (404, 410, 422, 500, 502, 503, 504):
                continue
            continue
        except Exception as e:
            detail = _hf_error_detail(e)
            last_error = detail
            logger.warning("HF image gen exception model=%s provider=%s detail=%s", model, provider, detail)
            if (
                "deprecated" in detail.lower()
                or "not supported by provider" in detail.lower()
                or "no longer supported" in detail.lower()
            ):
                continue
            continue

    return json.dumps(
        {
            "error": (
                f"Hugging Face image generation failed for {model}. "
                f"Last error: {last_error or 'unknown'}."
            )
        }
    )


async def run_image_gen(user_id: str, prompt: str) -> str:
    if not prompt or not prompt.strip():
        return json.dumps({"error": "Prompt is required"})

    logger.info("Image gen request: prompt=%r", prompt[:80])

    # Try Gemini first (if key configured).
    gemini_key = await get_api_key("gemini_api_key") or await get_api_key("google_ai_key")
    hf_key = await get_api_key("huggingface_api_key")
    if gemini_key:
        result = await _run_gemini(gemini_key, prompt)
        if result is not None:
            return result
        logger.info("Falling back to Hugging Face FLUX.1-dev for image gen")

    # Fallback: Hugging Face FLUX.1-dev
    if hf_key:
        return await _run_huggingface(hf_key, prompt)
    if gemini_key:
        return json.dumps(
            {
                "error": (
                    "Gemini image generation is unavailable and Hugging Face fallback is not configured. "
                    "Add Hugging Face API key in Settings (huggingface_api_key)."
                )
            }
        )
    return json.dumps(
        {
            "error": (
                "No image generation provider configured. "
                "Add a Gemini API key and/or Hugging Face API key in Settings."
            )
        }
    )
