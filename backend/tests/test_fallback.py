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
    """Auth failure on primary should fallback."""
    primary = MockProvider("primary", error="Auth failed", error_type=ProviderError.AUTH)
    fallback = MockProvider("fallback", response="Fallback")
    
    # We need to mock get_provider to return our fallback
    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(primary, [], ["fallback"])
    assert resp.content == "Fallback"
    assert used is not None and used.name == "fallback"

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


class _RuntimeStateDB:
    def __init__(self, *, states=None):
        self.states = states or {}
        self.auto_disabled: dict[str, str] = {}
        self.cleared: list[str] = []

    async def get_provider_runtime_states(self, user_id: str, providers):
        out = {}
        for p in providers:
            out[p] = self.states.get(
                p,
                {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
            )
        return out

    async def mark_provider_auto_disabled(self, user_id: str, provider: str, reason: str):
        self.auto_disabled[provider] = reason
        self.states[provider] = {
            "enabled": True,
            "auto_disabled": True,
            "disabled_reason": reason,
        }

    async def clear_provider_auto_disabled(self, user_id: str, provider: str):
        self.cleared.append(provider)
        state = self.states.get(
            provider,
            {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
        )
        state["auto_disabled"] = False
        state["disabled_reason"] = ""
        self.states[provider] = state


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


@pytest.mark.asyncio
async def test_stream_emits_lifecycle_events_per_provider_attempt():
    primary = MockProvider("primary", stream_error="timeout", stream_error_type=ProviderError.TIMEOUT)
    fallback = MockProvider("fallback", stream_chunks=["Fallback stream"])
    events: list[dict] = []

    async def _on_event(payload: dict) -> None:
        events.append(payload)

    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback_stream(
            primary,
            [],
            ["fallback"],
            on_stream_event=_on_event,
        )

    assert resp.content == "Fallback stream"
    assert used is not None and used.name == "fallback"
    starts = [e for e in events if str(e.get("type")) == "message_start"]
    assert len(starts) == 2
    assert starts[0].get("provider") == "primary"
    assert starts[1].get("provider") == "fallback"
    assert any(str(e.get("type")) == "text_delta" and e.get("provider") == "fallback" for e in events)
    assert any(str(e.get("type")) == "message_end" and e.get("provider") == "fallback" for e in events)


@pytest.mark.asyncio
async def test_auth_failure_falls_back_and_auto_disables_provider():
    primary = MockProvider(
        "claude",
        error="Your credit balance is too low. Please go to Plans & Billing.",
        error_type=ProviderError.AUTH,
    )
    fallback = MockProvider("openrouter", response="Fallback Success")
    runtime_db = _RuntimeStateDB()

    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(
            primary,
            [],
            ["openrouter"],
            _runtime_db=runtime_db,
            _runtime_user_id="default",
        )

    assert resp.content == "Fallback Success"
    assert used is not None and used.name == "openrouter"
    assert runtime_db.auto_disabled.get("claude") == "billing"


@pytest.mark.asyncio
async def test_disabled_primary_skips_to_fallback():
    primary = MockProvider("claude", response="primary should be skipped")
    fallback = MockProvider("openrouter", response="Fallback Success")
    runtime_db = _RuntimeStateDB(
        states={
            "claude": {"enabled": False, "auto_disabled": False, "disabled_reason": ""},
            "openrouter": {"enabled": True, "auto_disabled": False, "disabled_reason": ""},
        }
    )

    with unittest.mock.patch("app.providers.registry.get_provider", return_value=fallback):
        resp, used = await chat_with_fallback(
            primary,
            [],
            ["openrouter"],
            _runtime_db=runtime_db,
            _runtime_user_id="default",
        )

    assert resp.content == "Fallback Success"
    assert used is not None and used.name == "openrouter"