"""Base interface for AI providers. Implement one module per provider."""
from abc import ABC, abstractmethod
from typing import TypedDict


class Message(TypedDict):
    role: str  # "user" | "assistant" | "system"
    content: str


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> str:
        """Send messages and return assistant reply."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider id, e.g. 'ollama', 'claude', 'google'."""
        ...
