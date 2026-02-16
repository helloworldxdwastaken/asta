from app.channels.telegram_bot import _thinking_options, _thinking_text, build_telegram_app


def test_thinking_text_shows_current_level_and_options():
    text = _thinking_text("high")
    assert "Current thinking level: high" in text
    assert "Options: off, minimal, low, medium, high, xhigh" in text
    assert "/think <level>" in text
    assert "/thinking" in text
    assert "/t" in text


def test_thinking_options_hide_xhigh_for_unsupported_model():
    options = _thinking_options("openai", "gpt-4o-mini")
    assert "xhigh" not in options


def test_thinking_options_include_xhigh_for_supported_model():
    options = _thinking_options("openai", "gpt-5.2")
    assert "xhigh" in options


def test_telegram_registers_think_command_aliases():
    app = build_telegram_app("123:ABC")
    commands: set[str] = set()
    for handlers in app.handlers.values():
        for handler in handlers:
            cmd = getattr(handler, "commands", None)
            if cmd:
                commands.update(str(c).lower() for c in cmd)
    assert "think" in commands
    assert "thinking" in commands
    assert "t" in commands
