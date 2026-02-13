"""Telegram bot: receive messages, call handler, reply. Runs in FastAPI event loop (no thread)."""
import logging
import re
from urllib.parse import urlparse

import httpx
from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, AIORateLimiter
import asyncio
from collections import defaultdict
import html

# Locks to ensure sequential processing per chat
_chat_locks = defaultdict(asyncio.Lock)

from app.handler import handle_message

logger = logging.getLogger(__name__)


def to_telegram_format(text: str) -> str:
    """Convert common Markdown bits to Telegram HTML."""
    if not text:
        return ""
    # First escape the raw text so we don't accidentally send biohazard HTML
    text = html.escape(text)

    # Bold: **text** -> <b>text</b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    # Bold: __text__ -> <b>text</b> (if not inside word?)
    text = re.sub(r"__(.*?)__", r"<b>\1</b>", text)
    
    # Italic: *text* -> <i>text</i>
    # We use a refined regex to avoid matching things like multiplication or URLs
    text = re.sub(r"(?<!\*)\*(?!\s)(.*?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    # Italic: _text_ -> <i>text</i>
    text = re.sub(r"(?<!_)_(?!\s)(.*?)(?<!\s)_(?!_)", r"<i>\1</i>", text)

    # Code: `text` -> <code>text</code>
    text = re.sub(r"`(.*?)`", r"<code>\1</code>", text)

    # Code blocks: ```text``` -> <pre>text</pre>
    # Note: re.DOTALL to match across lines
    text = re.sub(r"```(.*?)```", r"<pre>\1</pre>", text, flags=re.DOTALL)

    return text


async def _reply_text_safe_html(message, text: str) -> None:
    """Reply using HTML formatting; fallback to plain text if Telegram rejects entities."""
    plain = (text or "").strip()[:TELEGRAM_MAX_MESSAGE_LENGTH] or "No response."
    formatted = to_telegram_format(plain)
    try:
        await message.reply_text(
            formatted,
            parse_mode=constants.ParseMode.HTML,
        )
    except Exception as e:
        msg = str(e).lower()
        if "parse entities" in msg or "unmatched end tag" in msg:
            logger.warning("Telegram HTML parse failed, falling back to plain text: %s", e)
            await message.reply_text(plain)
            return
        raise


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


def _telegram_user_allowed(update: Update) -> bool:
    """OpenClaw-style allowlist: if ASTA_TELEGRAM_ALLOWED_IDS is set, only those user IDs can use the bot."""
    from app.config import get_settings
    allowed = get_settings().telegram_allowed_ids
    if not allowed:
        return True
    user = update.effective_user if update else None
    if not user:
        return False
    return str(user.id) in allowed


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    # Same user as web panel (personal assistant: one user for all channels)
    user_id = "default"
    chat_id = update.effective_chat.id if update.effective_chat else 0
    
    # Acquire lock for this chat to prevent race conditions (sequential processing)
    # This matches OpenClaw's "sequentialize" behavior.
    async with _chat_locks[chat_id]:
        chat_id_str = str(chat_id)
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
                channel_target=chat_id_str,
            )
            
            # Check for markdown GIF (Giphy or .gif) and send as animation
            # Regex matches ![alt](url) where url contains giphy.com or ends in .gif
            gif_match = re.search(r"!\[.*?\]\((https?://(?:media\d?\.giphy\.com/media/|.*\.gif).*?)\)", reply)
            
            if gif_match:
                gif_url = gif_match.group(1)
                # Remove the markdown image from the text to avoid duplicate/ugly link
                text_reply = reply.replace(gif_match.group(0), "").strip()
                
                if text_reply:
                    await _reply_text_safe_html(update.message, text_reply)
                
                try:
                    await update.message.reply_animation(gif_url)
                    logger.info("Telegram reply sent to %s (with animation)", user_id)
                except Exception as e:
                    logger.warning("Failed to send animation to %s: %s", user_id, e)
                    # Fallback: if we haven't sent text yet (e.g. only gif), send the link
                    if not text_reply:
                        await update.message.reply_text(gif_url)
            else:
                out = (reply or "").strip()[:TELEGRAM_MAX_MESSAGE_LENGTH] or "No response."
                await _reply_text_safe_html(update.message, out)
                logger.info("Telegram reply sent to %s", user_id)
        except Exception as e:
            logger.exception("Telegram handler error")
            err_text = f"Error: {str(e)[:500]}"
            await update.message.reply_text(err_text)
            # Persist user + error so web UI Telegram preview shows the same as Telegram (handler may have saved user already; duplicate is ok)
            try:
                from app.db import get_db
                db = get_db()
                await db.connect()
                cid = await db.get_or_create_conversation("default", "telegram")
                await db.add_message(cid, "user", text)
                await db.add_message(cid, "assistant", err_text, None)
            except Exception as db_err:
                logger.warning("Could not persist Telegram error to DB: %s", db_err)



async def on_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages and audio files: transcribe and format as meeting notes."""
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    # Same user as web panel (personal assistant: one user for all channels)
    user_id = "default"
    chat_id = update.effective_chat.id if update.effective_chat else 0
    
    async with _chat_locks[chat_id]:
        chat_id_str = str(chat_id)
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
        await _reply_text_safe_html(update.message, out)
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
    # Use AIORateLimiter to respect Telegram limits (30 msg/sec, etc.)
    # This automatically handles 429s with backoff.
    rate_limiter = AIORateLimiter(overall_max_rate=30, overall_time_period=1)
    app = Application.builder().token(token.strip()).rate_limiter(rate_limiter).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice_or_audio))
    app.add_handler(MessageHandler(filters.Document.AUDIO, on_voice_or_audio))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return app


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos: download highest res, then call handle_message with image_bytes."""
    if not update.message or not update.message.photo:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    user_id = "default"
    chat_id = update.effective_chat.id if update.effective_chat else 0

    async with _chat_locks[chat_id]:
        chat_id_str = str(chat_id)
        # Fetch the largest available photo version
        photo = update.message.photo[-1]
        text = (update.message.caption or "").strip() or "What is in this image?"

        logger.info("Telegram photo from %s: %s", user_id, text)
        try:
            await update.message.reply_text("Taking a look… 🔍")
            await update.message.chat.send_action("typing")
            
            tg_file = await context.bot.get_file(photo.file_id)
            buf = await tg_file.download_as_bytearray()
            image_bytes = bytes(buf)
            image_mime = "image/jpeg" # Telegram photos are usually JPEGs

            reply = await handle_message(
                user_id, "telegram", text, provider_name="default",
                channel_target=chat_id_str,
                image_bytes=image_bytes,
                image_mime=image_mime
            )
            
            out = (reply or "").strip()[:TELEGRAM_MAX_MESSAGE_LENGTH] or "No response."
            await _reply_text_safe_html(update.message, out)
            logger.info("Telegram photo reply sent to %s", user_id)
        except Exception as e:
            logger.exception("Telegram photo handler error")
            await update.message.reply_text(f"Error: {str(e)[:500]}")



async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command directly (bypass AI for deterministic response)."""
    if not update.message:
        return
    
    from app.server_status import get_server_status
    ss = get_server_status()
    
    if ss.get("ok"):
        text = (
            f"<b>🖥️ Server Status</b> (v{ss.get('version', '?')})\n\n"
            f"<b>CPU:</b> {ss['cpu_percent']}%\n"
            f"<b>RAM:</b> {ss['ram']['percent']}% ({ss['ram']['used_gb']}GB / {ss['ram']['total_gb']}GB)\n"
            f"<b>Disk:</b> {ss['disk']['percent']}% ({ss['disk']['used_gb']}GB / {ss['disk']['total_gb']}GB)\n"
            f"<b>Uptime:</b> {ss['uptime_str']}"
        )
    else:
        text = f"<b>⚠️ Status Check Failed</b>\n{ss.get('error')}"
        
    await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)


async def start_telegram_bot_in_loop(app: Application) -> None:
    """Initialize and start polling + processor. Run inside FastAPI lifespan (same event loop)."""
    await app.initialize()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await app.start()
    logger.info("Telegram bot polling started (same loop as FastAPI)")
