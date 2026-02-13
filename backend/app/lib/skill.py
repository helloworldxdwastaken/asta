from abc import ABC, abstractmethod
from typing import Any

class Skill(ABC):
    """Abstract base class for Asta skills."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The internal name/ID of the skill (e.g., 'spotify', 'weather')."""
        pass

    @property
    def is_always_enabled(self) -> bool:
        """If True, this skill cannot be disabled by the user."""
        return False

    @abstractmethod
    def check_eligibility(self, text: str, user_id: str) -> bool:
        """
        Check if the skill should be triggered based on the user's message.
        """
        pass

    async def execute(self, user_id: str, text: str, extra: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the skill's logic.
        Returns a dictionary of data to be added to the 'extra' context.
        """
        return {}
        
    async def get_context_section(self, db, user_id: str, extra: dict[str, Any]) -> str | None:
         """
         Return the context string for this skill to be injected into the prompt.
         This replaces the monolithic _get_skill_section functions in context.py.
         """
         return None
