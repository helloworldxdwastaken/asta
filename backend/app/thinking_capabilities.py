"""Thinking capability detection for various AI providers and models."""
from typing import Any


# Models that support xhigh (extended reasoning/thinking)
_XHIGH_MODEL_REFS: tuple[str, ...] = (
    # OpenAI models
    "openai/gpt-5.2",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "openai-codex/gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex",
    "github-copilot/gpt-5.2-codex",
    "github-copilot/gpt-5.2",
    # Common models that support extended thinking
    "gpt-4-turbo",
    "gpt-4o",
    "gpt-4o-mini",
    "o1",
    "o1-mini",
    "o1-preview",
    "o3",
    "o3-mini",
    "claude-3-5-sonnet",
    "claude-3-5-sonnet-20241022",
    "claude-opus",
    "claude-4-opus",
    "claude-4-sonnet",
    "claude-sonnet",
    "claude-3.5-sonnet",
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
    # Trinity models (via OpenRouter)
    "trinity",
    "trinity-large-preview",
    "arcee-ai/trinity",
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
    # OpenAI models with extended thinking support
    if provider_key in ("openai",):
        if any(x in model_key for x in ("gpt-4-turbo", "gpt-4o", "o1-", "gpt-4-extended", "o3", "o4", "codex")):
            return True
    
    # Anthropic Claude models with extended thinking
    if provider_key in ("anthropic", "claude"):
        if any(x in model_key for x in ("claude-3-5", "claude-opus", "claude-3.5", "claude-4-", "claude-sonnet")):
            return True
    
    # OpenRouter: check if it's a Claude/OpenAI model that supports it
    if provider_key == "openrouter":
        if any(x in model_key for x in ("claude-3-5", "claude-opus", "gpt-4-turbo", "gpt-4o", "o1", "o3", "claude-sonnet")):
            return True
    
    # Qwen models with thinking/reasoning capabilities
    if "qwen" in model_key:
        # Qwen2.5 models and Qwen3 models support extended thinking
        if any(x in model_key for x in ("qwen2.5", "qwen3", "qwen2.5-coder", "qwen2.5-math", "qwen3-235b", "thinking")):
            return True
    
    # MiniMax models with thinking/reasoning capabilities
    if "minimax" in model_key:
        return True
    
    # Trinity models with thinking/reasoning capabilities  
    if "trinity" in model_key:
        return True
    
    return False


def get_thinking_options(provider: str | None, model: str | None) -> tuple[str, ...]:
    """Get available thinking level options for a given provider/model.
    
    Returns ("off", "minimal", "low", "medium", "high") by default,
    or adds "xhigh" if the model supports extended thinking.
    """
    base = ("off", "minimal", "low", "medium", "high")
    return base + (("xhigh",) if supports_xhigh_thinking(provider, model) else ())
