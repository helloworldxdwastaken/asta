"""Shared logic: transcribe audio and format as meeting notes (used by API and Telegram)."""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Awaitable, Callable

from app.audio_transcribe import transcribe_audio
from app.db import get_db
from app.providers.registry import get_provider

logger = logging.getLogger(__name__)

DEFAULT_INSTRUCTION = "Format this as meeting notes with bullet points, action items, and key decisions."


def _is_meeting_instruction(instruction: str) -> bool:
    """True if this looks like a meeting-notes request (we save these for later 'last meeting' queries)."""
    t = (instruction or "").strip().lower()
    if not t:
        return False
    return "meeting" in t


async def process_audio_to_notes(
    data: bytes,
    filename: str | None = None,
    instruction: str = "",
    user_id: str = "default",
    whisper_model: str = "base",
    progress_callback: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, str]:
    """Transcribe audio and format with AI. Returns {"transcript": str, "formatted": str}.
    If progress_callback is set, awaits it with "transcribing" then "formatting".
    Raises ValueError if skill disabled or transcription fails."""
    async def _progress(stage: str) -> None:
        if progress_callback:
            await progress_callback(stage)

    db = get_db()
    await db.connect()
    enabled = await db.get_skill_enabled(user_id, "audio_notes")
    if not enabled:
        raise ValueError("Audio notes skill is disabled. Enable it in Settings → Skills.")
    instruction = (instruction or DEFAULT_INSTRUCTION).strip() or DEFAULT_INSTRUCTION
    await _progress("transcribing")
    transcript = await transcribe_audio(data, filename, model=whisper_model)
    if not transcript or transcript == "(no speech detected)":
        return {"transcript": transcript or "", "formatted": "No speech detected in the audio."}

    provider_name = await db.get_user_default_ai(user_id)
    provider = get_provider(provider_name) or get_provider("groq") or get_provider("ollama")
    if not provider:
        return {
            "transcript": transcript,
            "formatted": "No AI provider available. Set an API key in Settings.",
        }
    user_model = await db.get_user_provider_model(user_id, provider.name)
    system = (
        "You are helping format a transcript from an audio recording. The user asked you to: "
        + instruction
        + "\n\nFormat the transcript accordingly. Use bullet points for meeting notes, clear sections for conversation summaries. Be concise. Output only the formatted content, no preamble."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": transcript},
    ]
    await _progress("formatting")
    try:
        formatted = await provider.chat(messages, model=user_model or None)
    except Exception as e:
        logger.exception("AI format failed: %s", e)
        return {"transcript": transcript, "formatted": f"Formatting failed: {e}"}
    formatted = (formatted or "").strip()

    # Save as "meeting" when instruction is meeting notes (so user can ask "last meeting?" later)
    if _is_meeting_instruction(instruction) and formatted and transcript != "(no speech detected)":
        try:
            title = "Meeting " + datetime.now().strftime("%Y-%m-%d %H:%M")
            await db.save_audio_note(user_id, title, transcript, formatted)
            logger.info("Saved audio note as meeting for user %s: %s", user_id, title)
        except Exception as e:
            logger.warning("Could not save audio note: %s", e)

    return {"transcript": transcript, "formatted": formatted}
