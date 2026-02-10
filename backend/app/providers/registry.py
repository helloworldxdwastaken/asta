"""Provider registry: get provider by name."""
from app.providers.base import BaseProvider
from app.providers.ollama import OllamaProvider
from app.providers.groq import GroqProvider
from app.providers.google import GoogleProvider
from app.providers.claude import ClaudeProvider
from app.providers.openai import OpenAIProvider
from app.providers.openrouter import OpenRouterProvider

_providers: dict[str, BaseProvider] = {
    "ollama": OllamaProvider(),
    "groq": GroqProvider(),
    "google": GoogleProvider(),
    "claude": ClaudeProvider(),
    "openai": OpenAIProvider(),
    "openrouter": OpenRouterProvider(),
}


def get_provider(name: str) -> BaseProvider | None:
    return _providers.get(name)


def list_providers() -> list[str]:
    return list(_providers.keys())
