"""Thinking capability detection for various AI providers and models."""


def supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    """Check if provider/model supports xhigh thinking level (extended reasoning).
    
    Known to support xhigh:
    - OpenAI: gpt-4-turbo, gpt-4o, gpt-4o-mini (with extended thinking)
    - Anthropic: claude-3-5-sonnet, claude-opus
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
    
    provider_lower = provider.lower()
    model_lower = model.lower()
    
    # OpenAI models with extended thinking support
    if provider_lower in ("openai",):
        # GPT-4 Turbo, GPT-4o, o1 family support extended thinking
        if any(x in model_lower for x in ("gpt-4-turbo", "gpt-4o", "o1-", "gpt-4-extended")):
            return True
    
    # Anthropic Claude models with extended thinking
    if provider_lower in ("anthropic", "claude"):
        # Claude 3.5 Sonnet and Opus support extended thinking
        if any(x in model_lower for x in ("claude-3-5", "claude-opus", "claude-3.5")):
            return True
    
    # OpenRouter: check if it's a Claude/OpenAI model that supports it
    if provider_lower == "openrouter":
        # Models via OpenRouter that support extended thinking
        if any(x in model_lower for x in ("claude-3-5", "claude-opus", "gpt-4-turbo", "gpt-4o", "o1")):
            return True
    
    # Conservative: return False for unknown providers or basic models
    return False
