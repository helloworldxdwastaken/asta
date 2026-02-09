"""Transcribe audio to text using faster-whisper (local, free, no API key)."""
from __future__ import annotations
import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Allowed MIME types / extensions for upload
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".mpeg"}
MAX_FILE_SIZE_MB = 50


def _get_suffix(filename: str | None) -> str:
    if filename:
        p = Path(filename)
        if p.suffix.lower() in AUDIO_EXTENSIONS:
            return p.suffix.lower()
    return ".webm"


# Allowed Whisper model names: tiny, base, small, medium, large-v2, large-v3 (base = fast, medium = more accurate)
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v2", "large-v3")


def _transcribe_sync(path: str, model_name: str = "base") -> str:
    """Blocking transcription (run in thread)."""
    from faster_whisper import WhisperModel
    if model_name not in WHISPER_MODELS:
        model_name = "base"
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, _ = model.transcribe(path)
    return " ".join(s.text for s in segments if s.text).strip() or "(no speech detected)"


async def transcribe_audio(data: bytes, filename: str | None = None, model: str = "base") -> str:
    """Transcribe audio bytes to text. Uses faster-whisper (local model).
    Raises ValueError if format unsupported or transcription fails."""
    if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"Audio file too large (max {MAX_FILE_SIZE_MB} MB).")
    suffix = _get_suffix(filename)
    if suffix not in AUDIO_EXTENSIONS:
        suffix = ".webm"
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError:
        raise ValueError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from None
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        model_name = (model or "base").strip().lower()
        if model_name not in WHISPER_MODELS:
            model_name = "base"
        text = await asyncio.to_thread(_transcribe_sync, path, model_name)
        return text or "(no speech detected)"
    except Exception as e:
        logger.exception("Transcription failed: %s", e)
        raise ValueError(f"Transcription failed: {e}") from e
    finally:
        Path(path).unlink(missing_ok=True)
