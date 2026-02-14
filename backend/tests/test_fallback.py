"""Tests for cross-provider model fallback using ProviderResponse."""
import pytest
import unittest
from unittest.mock import AsyncMock, MagicMock
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.providers.fallback import chat_with_fallback

class MockProvider(BaseProvider):
    def __init__(self, name, response=None, error=None, error_type=None):
        self._name = name
        self.response_content = response
        self.error_type = error_type
        self.error_msg = error
        
    @property
    def name(self):
        return self._name
        
    async def chat(self, messages, **kwargs):
        if self.error_type:
            return ProviderResponse(content="", error=self.error_type, error_message=self.error_msg)
        return ProviderResponse(content=self.response_content or "Success")

@pytest.mark.asyncio
async def test_primary_success():
    """Test standard success case."""
    primary = MockProvider("primary", response="Hello")
    resp, used = await chat_with_fallback(primary, [], [])
    assert resp.content == "Hello"
    assert resp.error is None
    assert used is not None and used.name == "primary"

@pytest.mark.asyncio
async def test_primary_auth_failure():
    """Auth failure on primary should NOT fallback."""
    primary = MockProvider("primary", error="Auth failed", error_type=ProviderError.AUTH)
    fallback = MockProvider("fallback", response="Fallback")
    
    # We need to mock get_provider to return our fallback
    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(primary, [], ["fallback"])
    assert resp.error == ProviderError.AUTH
    assert resp.content == ""
    assert used is None

@pytest.mark.asyncio
async def test_primary_transient_failure_with_fallback():
    """Transient failure on primary SHOULD trigger fallback."""
    primary = MockProvider("primary", error="Timeout", error_type=ProviderError.TIMEOUT)
    fallback = MockProvider("fallback", response="Fallback Success")
    
    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(primary, [], ["fallback"])
    assert resp.content == "Fallback Success"
    assert resp.error is None
    assert used is not None and used.name == "fallback"

@pytest.mark.asyncio
async def test_all_fail():
    """If all fail, return the last error."""
    primary = MockProvider("primary", error="Timeout", error_type=ProviderError.TIMEOUT)
    fallback = MockProvider("fallback", error="Rate Limit", error_type=ProviderError.RATE_LIMIT)
    
    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(primary, [], ["fallback"])
    assert resp.error == ProviderError.RATE_LIMIT
    assert "Rate Limit" in resp.error_message
    assert used is None
