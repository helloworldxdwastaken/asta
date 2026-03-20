"""Test security redaction functions."""

from app.handler_security import (
    _strip_shell_command_leakage,
    _redact_local_paths,
    _dedupe_secret_values,
)


# ── _strip_shell_command_leakage ──────────────────────────────────────────

def test_strip_shell_removes_cd_command():
    reply = "Here's what I found:\ncd /some/dir\nThe file is there."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert "cd /some/dir" not in cleaned
    assert "The file is there." in cleaned


def test_strip_shell_removes_git_command():
    reply = "Try this:\ngit push origin main\nThat should work."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert "git push" not in cleaned


def test_strip_shell_removes_npm_command():
    reply = "Install it:\nnpm install express\nDone."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert "npm install" not in cleaned


def test_strip_shell_removes_curl_command():
    reply = "Run:\ncurl https://example.com/api\nResult above."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert "curl" not in cleaned


def test_strip_shell_removes_devnull_redirect():
    reply = "Some text\nsome_command >/dev/null 2>&1\nDone."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert ">/dev/null" not in cleaned


def test_strip_shell_removes_chained_commands():
    reply = "Try:\nfoo && bar\nEnd."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is True
    assert "&&" not in cleaned


def test_strip_shell_preserves_clean_text():
    reply = "This is a normal response with no commands."
    cleaned, removed = _strip_shell_command_leakage(reply)
    assert removed is False
    assert cleaned == reply


def test_strip_shell_empty():
    cleaned, removed = _strip_shell_command_leakage("")
    assert cleaned == ""
    assert removed is False


# ── _redact_local_paths ───────────────────────────────────────────────────

def test_redact_unix_home_path():
    text = "The file is at /Users/tokyo/Documents/secret.txt"
    result = _redact_local_paths(text)
    assert "/Users/tokyo" not in result
    assert "[path]" in result


def test_redact_linux_home_path():
    text = "Located at /home/user/project/main.py"
    result = _redact_local_paths(text)
    assert "/home/user" not in result
    assert "[path]" in result


def test_redact_tilde_path():
    text = "See ~/Desktop/notes.md for details"
    result = _redact_local_paths(text)
    assert "~/Desktop" not in result
    assert "[path]" in result


def test_redact_windows_path():
    text = r"Found at C:\Users\admin\Documents\file.txt"
    result = _redact_local_paths(text)
    assert r"C:\Users" not in result
    assert "[path]" in result


def test_redact_preserves_generic_text():
    text = "Hello, this has no paths."
    result = _redact_local_paths(text)
    assert result == text


def test_redact_empty():
    assert _redact_local_paths("") == ""
    assert _redact_local_paths(None) == ""


# ── _dedupe_secret_values ─────────────────────────────────────────────────

def test_dedupe_basic():
    result = _dedupe_secret_values(["abcdef", "abcdef", "ghijkl"])
    assert len(result) == 2
    assert "abcdef" in result
    assert "ghijkl" in result


def test_dedupe_strips_whitespace():
    result = _dedupe_secret_values(["  abcdef  ", "abcdef"])
    assert len(result) == 1
    assert "abcdef" in result


def test_dedupe_filters_short():
    # Values shorter than 6 chars are excluded
    result = _dedupe_secret_values(["abc", "xy", "abcdefgh"])
    assert len(result) == 1
    assert "abcdefgh" in result


def test_dedupe_sorts_by_length_desc():
    result = _dedupe_secret_values(["short1", "longervalue1", "mediumval"])
    assert result[0] == "longervalue1"  # longest first


def test_dedupe_empty():
    assert _dedupe_secret_values([]) == []
