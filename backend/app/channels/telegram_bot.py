"""Telegram bot: receive messages, call handler, reply. Runs in FastAPI event loop (no thread)."""
import logging
from urllib.parse import urlparse

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from app.handler import handle_message

logger = logging.getLogger(__name__)

# Max length for a single Telegram message
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
# Max size when fetching audio from a URL (same as web panel)
MAX_AUDIO_URL_SIZE_MB = 50

# Extensions we accept for audio-from-URL
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".mp4", ".mpeg"}


def _is_audio_url(text: str) -> bool:
    """True if text looks like a single HTTP(S) URL (possibly with trailing instruction)."""
    line = (text or "").strip().split("\n")[0].strip()
    if not line.startswith(("http://", "https://")):
        return False
    try:
        parsed = urlparse(line)
        return bool(parsed.netloc and parsed.scheme in ("http", "https"))
    except Exception:
        return False


def _extract_url_and_instruction(text: str) -> tuple[str, str]:
    """If first line is URL, return (url, rest as instruction). Else ("", "")."""
    lines = [l.strip() for l in (text or "").strip().split("\n") if l.strip()]
    if not lines or not lines[0].startswith(("http://", "https://")):
        return "", ""
    url = lines[0]
    instruction = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
    return url, instruction


async def _fetch_audio_from_url(url: str) -> tuple[bytes, str] | None:
    """Fetch URL; if it looks like audio and size <= MAX_AUDIO_URL_SIZE_MB, return (data, filename). Else None."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # HEAD to check type and size
            head = await client.head(url)
            head.raise_for_status()
            content_type = (head.headers.get("content-type") or "").split(";")[0].strip().lower()
            content_length = head.headers.get("content-length")
            size = int(content_length) if content_length and content_length.isdigit() else 0
            if size > MAX_AUDIO_URL_SIZE_MB * 1024 * 1024:
                return None
            is_audio = content_type.startswith("audio/") or content_type in ("application/octet-stream", "video/mp4")
            path = urlparse(url).path or ""
            ext = path.lower().split(".")[-1] if "." in path else ""
            if not is_audio and ext not in ("mp3", "wav", "m4a", "ogg", "webm", "flac", "mp4", "mpeg"):
                return None
            # GET body
            r = await client.get(url)
            r.raise_for_status()
            data = r.content
            if len(data) > MAX_AUDIO_URL_SIZE_MB * 1024 * 1024:
                return None
            filename = path.split("/")[-1] if path else "audio"
            if not any(filename.lower().endswith(ext) for ext in AUDIO_EXTENSIONS):
                filename = filename or "audio.m4a"
            return (data, filename)
    except Exception as e:
        logger.warning("Failed to fetch audio URL %s: %s", url[:80], e)
        return None


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    # Same user as web panel (personal assistant: one user for all channels)
    user_id = "default"
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    text = update.message.text

    # If message is a single URL (optionally with instruction on next line), try to process as audio link (workaround for 20 MB Telegram limit)
    if _is_audio_url(text):
        url, instruction = _extract_url_and_instruction(text)
        if url:
            await update.message.reply_text("Downloading from link…")
            result = await _fetch_audio_from_url(url)
            if result:
                data, filename = result
                await update.message.reply_text("Transcribing…")
                async def _url_progress(stage: str) -> None:
                    if stage == "formatting":
                        await update.message.reply_text("Formatting…")
                try:
                    from app.audio_notes import process_audio_to_notes
                    out_result = await process_audio_to_notes(data, filename, instruction, user_id, progress_callback=_url_progress)
                    formatted = (out_result.get("formatted") or "").strip() or "No formatted output."
                    transcript = (out_result.get("transcript") or "").strip()
                    reply_text = formatted[:TELEGRAM_MAX_MESSAGE_LENGTH]
                    if len(formatted) > TELEGRAM_MAX_MESSAGE_LENGTH:
                        reply_text += "…"
                    await update.message.reply_text(reply_text)
                    if transcript and transcript != "(no speech detected)":
                        excerpt = transcript[:TELEGRAM_MAX_MESSAGE_LENGTH - 30] + ("…" if len(transcript) > TELEGRAM_MAX_MESSAGE_LENGTH - 30 else "")
                        await update.message.reply_text("📝 Transcript:\n" + excerpt)
                    logger.info("Telegram audio-from-URL sent to %s", user_id)
                    return
                except ValueError as e:
                    await update.message.reply_text(str(e)[:500])
                    return
                except Exception as e:
                    logger.exception("Audio notes from URL failed: %s", e)
                    await update.message.reply_text(f"Error: {str(e)[:500]}")
                    return
            await update.message.reply_text(
                "Could not use that link as audio (not a direct audio file or too large). "
                "Use a direct download link to an audio file (e.g. .m4a, .mp3), max 50 MB."
            )
            return

    logger.info("Telegram message from %s: %s", user_id, (text[:80] + "…") if len(text) > 80 else text)
    try:
        await update.message.chat.send_action("typing")
        reply = await handle_message(
            user_id, "telegram", text, provider_name="default",
            channel_target=chat_id,
        )
        out = (reply or "").strip()[:TELEGRAM_MAX_MESSAGE_LENGTH] or "No response."
        await update.message.reply_text(out)
        logger.info("Telegram reply sent to %s", user_id)
    except Exception as e:
        logger.exception("Telegram handler error")
        await update.message.reply_text(f"Error: {str(e)[:500]}")


async def on_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files: transcribe and format as meeting notes."""
    if not update.message:
        return
    # Same user as web panel (personal assistant: one user for all channels)
    user_id = "default"
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    # Caption as instruction (e.g. "meeting notes" or "action items")
    instruction = (update.message.caption or "").strip()
    file_id = None
    filename = "voice.ogg"
    if update.message.voice:
        file_id = update.message.voice.file_id
        filename = "voice.ogg"
    elif update.message.audio:
        file_id = update.message.audio.file_id
        filename = update.message.audio.file_name or "audio.mp3"
    elif update.message.document and update.message.document.mime_type and "audio" in update.message.document.mime_type:
        file_id = update.message.document.file_id
        filename = update.message.document.file_name or "audio"
    if not file_id:
        await update.message.reply_text("Send a voice message or an audio file. Add a caption like \"meeting notes\" or \"action items\" (optional).")
        return
    await update.message.reply_text("Transcribing…")
    try:
        tg_file = await context.bot.get_file(file_id)
        buf = await tg_file.download_as_bytearray()
        data = bytes(buf)
    except Exception as e:
        err = str(e).strip()
        logger.exception("Telegram file download failed: %s", e)
        if "too big" in err.lower() or "file is too big" in err.lower():
            await update.message.reply_text(
                "This file is too large (Telegram limit 20 MB). Workaround: upload the file elsewhere (e.g. Google Drive, Dropbox), get a direct download link, and paste that link here — I can process links up to 50 MB. Or use the web panel: Audio notes."
            )
        else:
            await update.message.reply_text(f"Could not download the file: {err[:300]}")
        return
    async def on_progress(stage: str) -> None:
        if stage == "formatting":
            await update.message.reply_text("Formatting…")

    try:
        from app.audio_notes import process_audio_to_notes
        result = await process_audio_to_notes(data, filename, instruction, user_id, progress_callback=on_progress)
    except ValueError as e:
        await update.message.reply_text(str(e)[:500])
        return
    except Exception as e:
        logger.exception("Audio notes failed: %s", e)
        await update.message.reply_text(f"Error: {str(e)[:500]}")
        return
    formatted = (result.get("formatted") or "").strip()
    transcript = (result.get("transcript") or "").strip()
    if not formatted:
        formatted = "No formatted output."
    out = formatted[:TELEGRAM_MAX_MESSAGE_LENGTH]
    if len(formatted) > TELEGRAM_MAX_MESSAGE_LENGTH:
        out = out + "…"
    await update.message.reply_text(out)
    if transcript and transcript != "(no speech detected)" and len(transcript) <= 500:
        await update.message.reply_text("📝 Transcript:\n" + transcript[:TELEGRAM_MAX_MESSAGE_LENGTH - 20])
    elif transcript and len(transcript) > 500:
        await update.message.reply_text("📝 Transcript (excerpt):\n" + transcript[:TELEGRAM_MAX_MESSAGE_LENGTH - 30] + "…")
    logger.info("Telegram audio notes sent to %s", user_id)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Hi, I'm Asta. Send me a message and I'll reply with context from your connected services. "
            "You can also send a voice message or audio file (or paste a direct link to an audio file for long recordings over 20 MB) — I'll transcribe and format as meeting notes."
        )


def build_telegram_app(token: str) -> Application:
    """Build configured Application (handlers only). Caller must initialize/start in same event loop."""
    app = Application.builder().token(token.strip()).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice_or_audio))
    app.add_handler(MessageHandler(filters.Document.AUDIO, on_voice_or_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app


async def start_telegram_bot_in_loop(app: Application) -> None:
    """Initialize and start polling + processor. Run inside FastAPI lifespan (same event loop)."""
    await app.initialize()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await app.start()
    logger.info("Telegram bot polling started (same loop as FastAPI)")
