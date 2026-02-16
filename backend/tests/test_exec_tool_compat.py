from app.config import get_settings
from app.exec_tool import parse_exec_arguments, prepare_allowlisted_command, run_allowlisted_command
import pytest


def test_parse_exec_arguments_normalizes_openclaw_aliases():
    parsed = parse_exec_arguments(
        {
            "command": "echo hi",
            "yieldMs": 500,
            "timeout": 12,
            "workDir": "~/workspace",
            "background": "true",
            "tty": "true",
        }
    )
    assert parsed["command"] == "echo hi"
    assert parsed["yield_ms"] == 500
    assert parsed["timeout_sec"] == 12
    assert parsed["workdir"] == "~/workspace"
    assert parsed["background"] is True
    assert parsed["pty"] is True


def test_parse_exec_arguments_accepts_timeoutsec_and_defaults_background_false():
    parsed = parse_exec_arguments('{"command":"echo ok","timeoutSec":"9"}')
    assert parsed["command"] == "echo ok"
    assert parsed["timeout_sec"] == 9
    assert parsed["background"] is False
    assert parsed["pty"] is False


def test_prepare_allowlisted_command_recommends_allow_command(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "allowlist")
    get_settings.cache_clear()
    argv, err = prepare_allowlisted_command("rg todo", allowed_bins={"memo"})
    assert argv is None
    assert err is not None
    assert "not in allowlist" in err
    assert "/allow rg" in err
    get_settings.cache_clear()


def test_prepare_allowlisted_command_reports_missing_binary(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "allowlist")
    get_settings.cache_clear()
    argv, err = prepare_allowlisted_command(
        "definitely_missing_binary_asta_xyz --version",
        allowed_bins={"definitely_missing_binary_asta_xyz"},
    )
    assert argv is None
    assert err is not None
    assert "not found in PATH" in err
    get_settings.cache_clear()


def test_prepare_allowlisted_command_normalizes_memo_notes_list(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "allowlist")
    get_settings.cache_clear()
    monkeypatch.setattr("app.exec_tool.resolve_executable", lambda name: "/usr/local/bin/memo" if name == "memo" else None)

    argv, err = prepare_allowlisted_command(
        'memo notes list -s "gift cards"',
        allowed_bins={"memo"},
    )

    assert err is None
    assert argv is not None
    assert argv[0] == "/usr/local/bin/memo"
    assert argv[1:] == ["notes", "-s", "gift cards"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_allowlisted_command_full_mode_supports_leading_comments(monkeypatch):
    monkeypatch.setenv("ASTA_EXEC_SECURITY", "full")
    get_settings.cache_clear()
    stdout, stderr, ok = await run_allowlisted_command(
        "# heading comment before command\necho asta-openclaw-style",
        allowed_bins=set(),
    )
    assert ok is True
    assert "asta-openclaw-style" in stdout
    assert stderr == ""
    get_settings.cache_clear()
