"""Thinking capability detection for various AI providers and models."""


def supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    """Check if provider/model supports xhigh thinking level (extended reasoning).
    
    Known to support xhigh:
    - OpenAI: gpt-4-turbo, gpt-4o, gpt-4o-mini (with extended thinking)
    - Anthropic: claude-3-5-sonnet, claude-opus
    - OpenRouter: models that support extended thinking (Claude, OpenAI, Kimi, Trinity)
    - Groq: generally does not support xhigh
    - Ollama: local models generally do not support xhigh, except specific thinking models (DeepSeek R1, Kimi)
    
    Args:
        provider: Provider name (e.g. "openai", "anthropic", "openrouter", "ollama")
        model: Model ID (e.g. "gpt-4", "claude-3-opus", "deepseek/deepseek-r1")
        
    Returns:
        bool: True if model supports xhigh thinking
    """
    if not provider or not model:
        return False
        
    prov = provider.strip().lower()
    mod = model.strip().lower()
    
    # OpenRouter
    if prov == "openrouter":
        # Known thinking models on OpenRouter
        if "claude-3-5-sonnet" in mod or "claude-3.7-sonnet" in mod:
            return True
        if "openai/o1" in mod or "openai/o3" in mod:
            return True
        if "deepseek/deepseek-r1" in mod:
            return True
        if "moonshot/moonshot-v1" in mod or "kimi" in mod:
            return True
        if "trinity" in mod:
            return True
        return False
        
    # OpenAI (native)
    if prov == "openai":
        return mod.startswith("o1") or mod.startswith("o3")
        
    # Anthropic (native)
    if prov == "anthropic":
        return "claude-3-7-sonnet" in mod or "claude-3-5-sonnet" in mod
        
    # Ollama (local)
    if prov == "ollama":
        if "deepseek-r1" in mod:
            return True
        if "kimi" in mod:
            return True
        return False
        
    return False
