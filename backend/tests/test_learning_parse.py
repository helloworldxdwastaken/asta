"""Test the /learn command parser."""

from app.handler_learning import _parse_learn_command


def test_parse_learn_topic():
    result = _parse_learn_command("/learn python decorators")
    assert result is not None
    action, args = result
    assert action == "learn"
    assert "python" in args
    assert "decorators" in args


def test_parse_learn_help():
    result = _parse_learn_command("/learn")
    assert result is not None
    action, args = result
    assert action == "help"
    assert args == []


def test_parse_learn_help_explicit():
    result = _parse_learn_command("/learn help")
    assert result is not None
    action, args = result
    assert action == "help"


def test_parse_learn_list():
    result = _parse_learn_command("/learn list")
    assert result is not None
    action, args = result
    assert action == "list"


def test_parse_learn_ls():
    result = _parse_learn_command("/learn ls")
    assert result is not None
    action, args = result
    assert action == "ls"


def test_parse_learn_delete():
    result = _parse_learn_command("/learn delete my-topic")
    assert result is not None
    action, args = result
    assert action == "delete"
    assert "my-topic" in args


def test_parse_learn_rm():
    result = _parse_learn_command("/learn rm old-topic")
    assert result is not None
    action, args = result
    assert action == "rm"
    assert "old-topic" in args


def test_parse_no_match():
    result = _parse_learn_command("what's the weather")
    assert result is None


def test_parse_no_match_empty():
    result = _parse_learn_command("")
    assert result is None


def test_parse_no_match_none():
    result = _parse_learn_command(None)
    assert result is None


def test_parse_learn_multi_word_topic():
    result = _parse_learn_command("/learn machine learning basics")
    assert result is not None
    action, args = result
    assert action == "learn"
    assert args == ["machine", "learning", "basics"]


def test_parse_learn_quoted_topic():
    result = _parse_learn_command('/learn "how to use asyncio"')
    assert result is not None
    action, args = result
    assert action == "learn"
    assert "how to use asyncio" in args
