"""Thinking capability detection for various AI providers and models."""
from typing import Any


# Models that support xhigh (extended reasoning/thinking)
_XHIGH_MODEL_REFS: tuple[str, ...] = (
    # OpenAI reasoning models (o-series + future gpt-5 — gpt-4o/gpt-4o-mini do NOT)
    "o1",
    "o1-mini",
    "o1-preview",
    "o3",
    "o3-mini",
    "o4-mini",
    "openai/gpt-5.2",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "openai-codex/gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex",
    "github-copilot/gpt-5.2-codex",
    "github-copilot/gpt-5.2",
    # Anthropic extended-thinking models (3.7+ only — 3.5 does NOT have extended thinking)
    "claude-3-7-sonnet",
    "claude-opus-4",
    "claude-sonnet-4",
    "claude-opus",
    "claude-4-opus",
    "claude-4-sonnet",
    # Moonshot / Kimi reasoning models
    "moonshot/moonshot-v1-8k",
    "moonshot/moonshot-v1-32k",
    "moonshot/moonshot-v1-128k",
    "moonshot-v1-8k",
    "moonshot-v1-32k",
    "moonshot-v1-128k",
    "kimi",
    # DeepSeek reasoning models
    "deepseek/deepseek-r1",
    "deepseek-r1",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1:70b",
    # Qwen models with thinking/reasoning support
    "qwen2.5-coder",
    "qwen2.5-coder:32b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b",
    "qwen2.5-math",
    "qwen2.5-math:72b",
    "qwen2.5:72b",
    "qwen2.5:32b",
    "qwen2.5:14b",
    "qwen2.5:7b",
    "qwen3",
    "qwen3:235b-a22b",
    "qwen3-235b-a22b-thinking",
    # MiniMax models (via OpenRouter or direct)
    "minimax-m2.5",
    "minimax-m2",
    "minimax",
    # Google Gemini models with thinking support (2.5+)
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
)

_XHIGH_MODEL_SET: set[str] = {ref.lower() for ref in _XHIGH_MODEL_REFS}
_XHIGH_MODEL_IDS: set[str] = {ref.split("/", 1)[1].lower() for ref in _XHIGH_MODEL_REFS if "/" in ref}


def supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    """Check if provider/model supports xhigh thinking level (extended reasoning).
    
    Known to support xhigh:
    - OpenAI: gpt-4-turbo, gpt-4o, gpt-4o-mini, o1 family, Codex models
    - Anthropic: claude-3-5-sonnet, claude-opus, claude-4 models
    - OpenRouter: models that support extended thinking (Claude, OpenAI via OpenRouter)
    - Groq: generally does not support xhigh
    - Ollama: local models generally do not support xhigh
    
    Args:
        provider: Provider name (e.g. "openai", "anthropic", "openrouter", "ollama")
        model: Model name/identifier
        
    Returns:
        True if the provider/model supports xhigh thinking level, False otherwise
    """
    if not provider or not model:
        return False
    
    model_key = (model or "").strip().lower()
    if not model_key:
        return False
    
    provider_key = (provider or "").strip().lower()
    
    # Check exact matches in the set
    if model_key in _XHIGH_MODEL_SET:
        return True
    
    # Check provider/model combination
    if provider_key and f"{provider_key}/{model_key}" in _XHIGH_MODEL_SET:
        return True
    
    # Check model ID without provider prefix
    if model_key in _XHIGH_MODEL_IDS:
        return True
    
    # Check if model ID matches when there's a "/" in the model ref
    if "/" in model_key and model_key.split("/", 1)[1] in _XHIGH_MODEL_IDS:
        return True
    
    # Additional pattern-based detection for common models
    # OpenAI: only o-series reasoning models support extended thinking
    if provider_key in ("openai",):
        if any(x in model_key for x in ("o1-", "o3-", "o4-")):
            return True

    # Anthropic Claude: 3.7+, claude-4, claude-opus
    if provider_key in ("anthropic", "claude"):
        if any(x in model_key for x in ("claude-3-7", "claude-3.7", "claude-4-", "claude-opus", "claude-sonnet-4")):
            return True

    # OpenRouter: moonshot/kimi, deepseek-r1, claude extended-thinking, o-series
    if provider_key == "openrouter":
        if any(x in model_key for x in ("moonshot", "kimi", "deepseek-r1", "claude-3-7", "claude-opus", "o1", "o3", "o4-")):
            return True

    # Ollama: deepseek-r1 and kimi reasoning models
    if provider_key == "ollama":
        if any(x in model_key for x in ("deepseek-r1", "kimi", "qwen2.5", "qwen3")):
            return True
    
    # Qwen models with thinking/reasoning capabilities
    if "qwen" in model_key:
        # Qwen2.5 models and Qwen3 models support extended thinking
        if any(x in model_key for x in ("qwen2.5", "qwen3", "qwen2.5-coder", "qwen2.5-math", "qwen3-235b", "thinking")):
            return True
    
    # MiniMax models with thinking/reasoning capabilities
    if "minimax" in model_key:
        return True

    # Google Gemini: 2.5+ and 3+ models support thinking
    if provider_key == "google" or "gemini" in model_key:
        if any(x in model_key for x in ("gemini-2.5", "gemini-3")):
            return True

    return False


def get_thinking_options(provider: str | None, model: str | None) -> tuple[str, ...]:
    """Get available thinking level options for a given provider/model.
    
    Returns ("off", "minimal", "low", "medium", "high") by default,
    or adds "xhigh" if the model supports extended thinking.
    """
    base = ("off", "minimal", "low", "medium", "high")
    return base + (("xhigh",) if supports_xhigh_thinking(provider, model) else ())
