import json

import pytest

from app.message_compat_tool import (
    parse_message_compat_args,
    run_message_compat,
)


def test_parse_message_compat_args_aliases():
    parsed = parse_message_compat_args(
        {
            "action": "send_attachment",
            "message": "hello",
            "target": "123",
            "messageId": 88,
            "replyTo": 77,
        }
    )
    assert parsed["action"] == "sendAttachment"
    assert parsed["text"] == "hello"
    assert parsed["to"] == "123"
    assert parsed["message_id"] == "88"
    assert parsed["reply_to"] == "77"


def test_parse_message_compat_args_send_poll_aliases():
    parsed = parse_message_compat_args(
        {
            "action": "send_poll",
            "question": "Lunch?",
            "options": "Pizza, Sushi, Salad",
            "duration_seconds": "120",
            "is_anonymous": False,
        }
    )
    assert parsed["action"] == "sendPoll"
    assert parsed["question"] == "Lunch?"
    assert parsed["durationSeconds"] == "120"
    assert parsed["isAnonymous"] is False


@pytest.mark.asyncio
async def test_run_message_compat_send_success(monkeypatch):
    sent = {}

    async def _fake_send(channel: str, target: str, message: str):
        sent["channel"] = channel
        sent["target"] = target
        sent["message"] = message

    monkeypatch.setattr("app.message_compat_tool.send_notification", _fake_send)
    raw = await run_message_compat(
        {"action": "send", "text": "hi"},
        current_channel="whatsapp",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["status"] == "sent"
    assert sent == {"channel": "whatsapp", "target": "42", "message": "hi"}


@pytest.mark.asyncio
async def test_run_message_compat_telegram_rich_action_dispatch(monkeypatch):
    async def _fake_telegram(action: str, chat_id: str, params: dict):
        assert action == "reply"
        assert chat_id == "42"
        assert params.get("reply_to") == "55"
        return {"ok": True, "status": "sent", "action": "reply", "message_id": 999}

    monkeypatch.setattr("app.message_compat_tool._run_telegram_message_action", _fake_telegram)
    params = parse_message_compat_args({"action": "reply", "text": "hi", "replyTo": "55"})
    raw = await run_message_compat(
        params,
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["action"] == "reply"
    assert payload["channel"] == "telegram"
    assert payload["target"] == "42"
    assert payload["message_id"] == 999


@pytest.mark.asyncio
async def test_run_message_compat_telegram_send_poll_dispatch(monkeypatch):
    async def _fake_telegram(action: str, chat_id: str, params: dict):
        assert action == "sendPoll"
        assert chat_id == "42"
        assert params.get("question") == "Lunch?"
        return {"ok": True, "status": "sent", "action": "sendPoll", "message_id": 321}

    monkeypatch.setattr("app.message_compat_tool._run_telegram_message_action", _fake_telegram)
    raw = await run_message_compat(
        {
            "action": "send_poll",
            "question": "Lunch?",
            "options": ["Pizza", "Sushi"],
        },
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["action"] == "sendPoll"
    assert payload["message_id"] == 321


@pytest.mark.asyncio
async def test_run_message_compat_canonicalizes_runtime_action(monkeypatch):
    observed = {}

    async def _fake_telegram(action: str, chat_id: str, params: dict):
        observed["action"] = action
        observed["chat_id"] = chat_id
        return {"ok": True, "status": "sent", "action": action, "message_id": 7}

    monkeypatch.setattr("app.message_compat_tool._run_telegram_message_action", _fake_telegram)
    raw = await run_message_compat(
        {"action": "send_attachment", "path": "/tmp/whatever"},
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert observed["action"] == "sendAttachment"
    assert observed["chat_id"] == "42"


@pytest.mark.asyncio
async def test_run_message_compat_rejects_cross_channel():
    raw = await run_message_compat(
        {"action": "send", "text": "hi", "channel": "whatsapp"},
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "Cross-channel" in payload["error"]


@pytest.mark.asyncio
async def test_run_message_compat_rejects_cross_target():
    raw = await run_message_compat(
        {"action": "send", "text": "hi", "to": "99"},
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "Cross-target" in payload["error"]


@pytest.mark.asyncio
async def test_run_message_compat_rejects_unsupported_action():
    raw = await run_message_compat(
        {"action": "mystery-action", "text": "hi"},
        current_channel="telegram",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "Unsupported action" in payload["error"]


@pytest.mark.asyncio
async def test_run_message_compat_rejects_rich_action_on_non_telegram():
    raw = await run_message_compat(
        {"action": "edit", "text": "hi", "messageId": "10"},
        current_channel="whatsapp",
        current_target="42",
    )
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert "not supported on channel" in payload["error"]
