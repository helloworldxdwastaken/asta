from app.config import get_settings
from app.exec_tool import parse_exec_arguments, prepare_allowlisted_command


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
