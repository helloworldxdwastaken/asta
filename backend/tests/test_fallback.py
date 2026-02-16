"""Tests for cross-provider model fallback using ProviderResponse."""
import pytest
import unittest
from unittest.mock import AsyncMock
from app.providers.base import BaseProvider, Message, ProviderResponse, ProviderError
from app.providers.fallback import chat_with_fallback, chat_with_fallback_stream

class MockProvider(BaseProvider):
    def __init__(
        self,
        name,
        response=None,
        error=None,
        error_type=None,
        stream_chunks=None,
        stream_error=None,
        stream_error_type=None,
    ):
        self._name = name
        self.response_content = response
        self.error_type = error_type
        self.error_msg = error
        self.stream_chunks = stream_chunks
        self.stream_error_type = stream_error_type
        self.stream_error_msg = stream_error

    @property
    def name(self):
        return self._name

    async def chat(self, messages, **kwargs):
        if self.error_type:
            return ProviderResponse(content="", error=self.error_type, error_message=self.error_msg)
        return ProviderResponse(content=self.response_content or "Success")

    async def chat_stream(self, messages, *, on_text_delta=None, **kwargs):
        if self.stream_error_type:
            return ProviderResponse(content="", error=self.stream_error_type, error_message=self.stream_error_msg)
        if isinstance(self.stream_chunks, list):
            if on_text_delta:
                for chunk in self.stream_chunks:
                    await on_text_delta(chunk)
            return ProviderResponse(content="".join(self.stream_chunks))
        return await super().chat_stream(messages, on_text_delta=on_text_delta, **kwargs)

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


class _NonStreamProvider:
    def __init__(self, name: str, content: str):
        self._name = name
        self._content = content

    @property
    def name(self):
        return self._name

    async def chat(self, messages, **kwargs):
        return ProviderResponse(content=self._content)


@pytest.mark.asyncio
async def test_stream_primary_success_emits_deltas():
    primary = MockProvider("primary", stream_chunks=["Hel", "lo"])
    on_delta = AsyncMock()

    resp, used = await chat_with_fallback_stream(primary, [], [], on_text_delta=on_delta)

    assert resp.content == "Hello"
    assert resp.error is None
    assert used is not None and used.name == "primary"
    assert [c.args[0] for c in on_delta.await_args_list] == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_stream_supports_non_stream_provider_via_chat():
    primary = _NonStreamProvider("primary", "fallback-to-chat")
    on_delta = AsyncMock()

    resp, used = await chat_with_fallback_stream(primary, [], [], on_text_delta=on_delta)

    assert resp.content == "fallback-to-chat"
    assert resp.error is None
    assert used is not None and used.name == "primary"
    assert [c.args[0] for c in on_delta.await_args_list] == ["fallback-to-chat"]


@pytest.mark.asyncio
async def test_stream_primary_failure_uses_fallback_provider():
    primary = MockProvider("primary", stream_error="timeout", stream_error_type=ProviderError.TIMEOUT)
    fallback = MockProvider("fallback", stream_chunks=["Fallback stream"])
    on_delta = AsyncMock()

    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback_stream(primary, [], ["fallback"], on_text_delta=on_delta)

    assert resp.content == "Fallback stream"
    assert resp.error is None
    assert used is not None and used.name == "fallback"
    assert [c.args[0] for c in on_delta.await_args_list] == ["Fallback stream"]
