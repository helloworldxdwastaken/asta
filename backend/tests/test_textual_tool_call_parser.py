import json

from app.handler import _extract_textual_tool_calls, _strip_tool_call_markup


def test_extract_textual_tool_calls_from_asta_tag():
    text = (
        'I will do it.\n'
        '[ASTA_TOOL_CALL]{"name":"read","arguments":{"path":"/tmp/a.txt"}}[/ASTA_TOOL_CALL]'
    )
    calls, cleaned = _extract_textual_tool_calls(text, {"read"})
    assert calls is not None
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "read"
    assert json.loads(calls[0]["function"]["arguments"]) == {"path": "/tmp/a.txt"}
    assert "[ASTA_TOOL_CALL]" not in cleaned


def test_extract_textual_tool_calls_from_xml_function_calls():
    text = """
<function_calls>
<invoke name="read">
<parameter name="path">/Users/tokyo/asta/workspace/skills/apple-notes/SKILL.md</parameter>
</invoke>
</function_calls>
"""
    calls, cleaned = _extract_textual_tool_calls(text, {"read"})
    assert calls is not None
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "read"
    assert json.loads(calls[0]["function"]["arguments"]) == {
        "path": "/Users/tokyo/asta/workspace/skills/apple-notes/SKILL.md"
    }
    assert "<function_calls>" not in cleaned


def test_extract_textual_tool_calls_respects_allowed_names():
    text = """
<function_calls>
<invoke name="read"><parameter name="path">/tmp/a.txt</parameter></invoke>
</function_calls>
"""
    calls, cleaned = _extract_textual_tool_calls(text, {"exec"})
    assert calls is None
    assert cleaned == text


def test_strip_tool_call_markup_removes_known_blocks():
    text = (
        "Before\n"
        '[ASTA_TOOL_CALL]{"name":"read","arguments":{"path":"/tmp/a.txt"}}[/ASTA_TOOL_CALL]\n'
        "<function_calls><invoke name=\"read\"><parameter name=\"path\">/tmp/a.txt</parameter></invoke></function_calls>\n"
        "After"
    )
    cleaned = _strip_tool_call_markup(text)
    assert "[ASTA_TOOL_CALL]" not in cleaned
    assert "<function_calls>" not in cleaned
    assert "Before" in cleaned
    assert "After" in cleaned
