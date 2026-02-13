"""Tests for the new Skill system and refactored context."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.skills.registry import get_all_skills, get_skill_by_name
from app.skill_router import get_skills_to_use
from app.lib.skill import Skill

# Mock DB
class MockDb:
    async def get_skill_enabled(self, user_id, skill_name):
        return True # All enabled by default for tests

@pytest.mark.asyncio
async def test_registry_loading():
    skills = get_all_skills()
    assert len(skills) > 0
    names = [s.name for s in skills]
    assert "time" in names
    assert "server_status" in names
    assert "weather" in names

@pytest.mark.asyncio
async def test_router_logic():
    # Test Time routing
    enabled = {"time", "weather", "server_status"}
    skills = get_skills_to_use("what time is it", enabled)
    assert "time" in skills
    assert "weather" not in skills
    
    # Test Server Status routing
    skills = get_skills_to_use("server status", enabled)
    assert "server_status" in skills
    
    # Test Weather routing
    skills = get_skills_to_use("what is the weather", enabled)
    assert "weather" in skills

@pytest.mark.asyncio
async def test_context_generation_mock():
    # Test that a skill produces context
    # We mock the _get_time_section helper to avoid real DB/Logic calls
    
    time_skill = get_skill_by_name("time")
    assert time_skill is not None
    
    mock_db = MockDb()
    
    with patch("app.context_helpers._get_time_section", new_callable=AsyncMock) as mock_helper:
        mock_helper.return_value = ["Time is 12:00"]
        
        ctx = await time_skill.get_context_section(mock_db, "user1", {})
        assert "Time is 12:00" in ctx
        mock_helper.assert_called_once()
