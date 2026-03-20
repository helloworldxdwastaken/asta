"""Test intent detection functions with real inputs."""

from app.handler_intent import (
    _is_exec_intent,
    _is_short_acknowledgment,
    _looks_like_image_generation_request,
    _looks_like_files_check_request,
    _looks_like_command_request,
    _is_note_capture_request,
    _is_workspace_notes_list_request,
    _is_explicit_apple_notes_request,
    _is_exec_check_request,
    _provider_supports_tools,
)


# ── _is_exec_intent ──────────────────────────────────────────────────────

def test_exec_intent_detects_apple_notes():
    assert _is_exec_intent("check my apple notes")


def test_exec_intent_detects_memo():
    assert _is_exec_intent("open memo and add a task")


def test_exec_intent_detects_things():
    assert _is_exec_intent("add to things inbox")


def test_exec_intent_rejects_generic():
    assert not _is_exec_intent("what's the weather")


def test_exec_intent_rejects_empty():
    assert not _is_exec_intent("")
    assert not _is_exec_intent(None)


# ── _is_short_acknowledgment ─────────────────────────────────────────────

def test_short_ack_basic():
    assert _is_short_acknowledgment("ok")
    assert _is_short_acknowledgment("thanks")
    assert _is_short_acknowledgment("yep")
    assert _is_short_acknowledgment("cool")
    assert _is_short_acknowledgment("great")


def test_short_ack_with_punctuation():
    assert _is_short_acknowledgment("ok.")
    assert _is_short_acknowledgment("thanks!")


def test_short_ack_rejects_long():
    assert not _is_short_acknowledgment("tell me about python programming")


def test_short_ack_rejects_empty():
    assert not _is_short_acknowledgment("")
    assert not _is_short_acknowledgment(None)


# ── _looks_like_image_generation_request ──────────────────────────────────

def test_image_gen_request():
    assert _looks_like_image_generation_request("generate an image of a cat")
    assert _looks_like_image_generation_request("create a logo for my company")
    assert _looks_like_image_generation_request("draw a picture of sunset")
    assert _looks_like_image_generation_request("design a poster for the event")


def test_image_gen_imagine_command():
    assert _looks_like_image_generation_request("/imagine a cat in space")
    assert _looks_like_image_generation_request("imagine a sunset")


def test_image_gen_rejects_questions():
    assert not _looks_like_image_generation_request("how do images work")
    assert not _looks_like_image_generation_request("do you have access to image generation tool")
    assert not _looks_like_image_generation_request("what model is best for images")


def test_image_gen_rejects_empty():
    assert not _looks_like_image_generation_request("")
    assert not _looks_like_image_generation_request(None)


# ── _looks_like_files_check_request ───────────────────────────────────────

def test_files_check_desktop():
    assert _looks_like_files_check_request("check my desktop for pdfs")
    assert _looks_like_files_check_request("what files are on my desktop")


def test_files_check_documents():
    assert _looks_like_files_check_request("find something in documents")


def test_files_check_rejects_generic():
    assert not _looks_like_files_check_request("what's the weather")


def test_files_check_rejects_write_operations():
    assert not _looks_like_files_check_request("create a file on desktop")
    assert not _looks_like_files_check_request("delete the file from downloads")


def test_files_check_rejects_empty():
    assert not _looks_like_files_check_request("")


# ── _is_note_capture_request ─────────────────────────────────────────────

def test_note_capture():
    assert _is_note_capture_request("take a note about the meeting")
    assert _is_note_capture_request("save this for later")
    assert _is_note_capture_request("add a note about project X")


def test_note_capture_rejects_list():
    assert not _is_note_capture_request("what notes do I have")


def test_note_capture_rejects_apple_notes():
    # Apple Notes requests are handled separately
    assert not _is_note_capture_request("take a note in apple notes")


def test_note_capture_rejects_empty():
    assert not _is_note_capture_request("")


# ── _is_workspace_notes_list_request ──────────────────────────────────────

def test_workspace_notes_list():
    assert _is_workspace_notes_list_request("what notes do I have")
    assert _is_workspace_notes_list_request("list notes")
    assert _is_workspace_notes_list_request("show notes")
    assert _is_workspace_notes_list_request("my notes")


def test_workspace_notes_list_rejects_capture():
    assert not _is_workspace_notes_list_request("take a note")


def test_workspace_notes_list_rejects_empty():
    assert not _is_workspace_notes_list_request("")


# ── _looks_like_command_request ───────────────────────────────────────────

def test_command_request():
    assert _looks_like_command_request("how to run a terminal command")
    assert _looks_like_command_request("install node on my mac")
    assert _looks_like_command_request("run this script please")


def test_command_request_rejects_generic():
    assert not _looks_like_command_request("what's the weather")
    assert not _looks_like_command_request("tell me about python")


# ── _is_explicit_apple_notes_request ──────────────────────────────────────

def test_apple_notes_explicit():
    assert _is_explicit_apple_notes_request("check my apple notes")
    assert _is_explicit_apple_notes_request("open notes.app")
    assert _is_explicit_apple_notes_request("save to icloud notes")


def test_apple_notes_explicit_rejects():
    assert not _is_explicit_apple_notes_request("take a note")
    assert not _is_explicit_apple_notes_request("")


# ── _is_exec_check_request ───────────────────────────────────────────────

def test_exec_check_request():
    assert _is_exec_check_request("check my apple notes")
    assert _is_exec_check_request("show my things inbox")


def test_exec_check_rejects_no_verb():
    # has exec intent but no check verb
    assert not _is_exec_check_request("add to things inbox please now")


# ── _provider_supports_tools ─────────────────────────────────────────────

def test_provider_supports_tools():
    assert _provider_supports_tools("openai")
    assert _provider_supports_tools("claude")
    assert _provider_supports_tools("ollama")
    assert not _provider_supports_tools("unknown_provider")
    assert not _provider_supports_tools("")
