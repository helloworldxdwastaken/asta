from app.exec_tool import parse_exec_arguments


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
