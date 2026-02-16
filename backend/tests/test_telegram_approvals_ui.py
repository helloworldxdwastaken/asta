from app.channels.telegram_bot import (
    _parse_approval_callback_data,
    _approval_actions_markup,
    _build_approval_resume_prompt,
    build_telegram_app,
)


def test_parse_approval_callback_data_accepts_valid_actions_and_id():
    assert _parse_approval_callback_data("approval:once:app_deadbeef") == ("once", "app_deadbeef")
    assert _parse_approval_callback_data("approval:always:app_deadbeef") == ("always", "app_deadbeef")
    assert _parse_approval_callback_data("approval:deny:app_deadbeef") == ("deny", "app_deadbeef")


def test_parse_approval_callback_data_rejects_invalid_payloads():
    assert _parse_approval_callback_data("") is None
    assert _parse_approval_callback_data("approval:approve:app_deadbeef") is None
    assert _parse_approval_callback_data("approval:once:xyz") is None
    assert _parse_approval_callback_data("approval:once:app_deadbeef42") is None


def test_approval_actions_markup_contains_three_buttons():
    markup = _approval_actions_markup("app_deadbeef")
    row = markup.inline_keyboard[0]
    labels = [btn.text for btn in row]
    payloads = [btn.callback_data for btn in row]

    assert labels == ["✅ Once", "✅ Always", "❌ Deny"]
    assert payloads == [
        "approval:once:app_deadbeef",
        "approval:always:app_deadbeef",
        "approval:deny:app_deadbeef",
    ]


def test_build_approval_resume_prompt_contains_ground_truth_instructions():
    prompt = _build_approval_resume_prompt(
        {
            "approval_id": "app_deadbeef",
            "mode": "once",
            "command": "rg todo",
            "output": "line 1\\nline 2",
            "error": "",
            "ok": True,
        }
    )
    assert "approval is done" in prompt.lower()
    assert "Do not ask the user to approve again." in prompt
    assert "Do not re-run the same command" in prompt
    assert "rg todo" in prompt
    assert "line 1" in prompt


def test_telegram_registers_approval_callback_handler():
    app = build_telegram_app("123:ABC")
    callback_patterns: set[str] = set()
    commands: set[str] = set()
    for handlers in app.handlers.values():
        for handler in handlers:
            pattern = getattr(handler, "pattern", None)
            if pattern is not None:
                callback_patterns.add(pattern.pattern)
            cmd = getattr(handler, "commands", None)
            if cmd:
                commands.update(str(c).lower() for c in cmd)

    assert "^approval:" in callback_patterns
    assert "approvals" in commands
    assert "approve" not in commands
    assert "deny" not in commands
