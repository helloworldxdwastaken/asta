from abc import ABC, abstractmethod
from typing import TypedDict, Any
from dataclasses import dataclass, field
from enum import Enum


class Message(TypedDict):
    role: str  # "user" | "assistant" | "system"
    content: str


class ProviderError(str, Enum):
    """Standardized error kinds for providers."""
    AUTH = "auth"                # API key invalid
    RATE_LIMIT = "rate_limit"    # Rate limited
    MODEL_NOT_FOUND = "model"    # Model doesn't exist
    TIMEOUT = "timeout"          # Timed out
    TRANSIENT = "transient"      # Unknown/transient error (connection reset, 500, etc)
    NONE = "none"                # (Not used in error field, but for logic)


@dataclass
class ProviderResponse:
    """Standardized response from an AI provider."""
    content: str
    error: ProviderError | None = None
    error_message: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> ProviderResponse:
        """Send messages and return assistant reply."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider id, e.g. 'ollama', 'claude', 'google'."""
        ...
