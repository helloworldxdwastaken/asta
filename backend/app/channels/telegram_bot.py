"""Telegram bot: receive messages, call handler, reply. Runs in FastAPI event loop (no thread)."""
import logging
import re
from urllib.parse import urlparse

import httpx
from telegram import (
    Update,
    constants,
    ReactionTypeEmoji,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    AIORateLimiter,
)
import asyncio
import html

# Locks to ensure sequential processing per chat
_chat_locks: dict[int, asyncio.Lock] = {}
_chat_locks_lock = asyncio.Lock()
MAX_CHAT_LOCKS = 1000  # Configurable threshold


def _cleanup_stale_locks() -> None:
    """Remove unlocked locks when dict grows too large (LRU-style).

    Called opportunistically on lock acquisition.
    """
    if len(_chat_locks) <= MAX_CHAT_LOCKS:
        return

    # Remove half the unlocked entries
    to_remove = []
    for chat_id, lock in list(_chat_locks.items()):
        if not lock.locked():
            to_remove.append(chat_id)
        if len(to_remove) >= MAX_CHAT_LOCKS // 2:
            break

    for chat_id in to_remove:
        _chat_locks.pop(chat_id, None)

    if to_remove:
        logger.debug("Cleaned up %d stale chat locks", len(to_remove))


async def _get_chat_lock(chat_id: int) -> asyncio.Lock:
    """Thread-safe chat lock factory with cleanup."""
    async with _chat_locks_lock:
        _cleanup_stale_locks()  # Opportunistic cleanup

        if chat_id not in _chat_locks:
            _chat_locks[chat_id] = asyncio.Lock()
        return _chat_locks[chat_id]

from app.handler import handle_message
from app.config import get_settings, set_env_value

logger = logging.getLogger(__name__)
_EXEC_MODES = ("deny", "allowlist", "full")
_THINK_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh")
_REASONING_MODES = ("off", "on", "stream")
_XHIGH_MODEL_REFS = (
    "openai/gpt-5.2",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "openai-codex/gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex",
    "github-copilot/gpt-5.2-codex",
    "github-copilot/gpt-5.2",
)
_XHIGH_MODEL_SET = {ref.lower() for ref in _XHIGH_MODEL_REFS}
_XHIGH_MODEL_IDS = {ref.split("/", 1)[1].lower() for ref in _XHIGH_MODEL_REFS if "/" in ref}
_ALLOW_COMMAND_HELP = "Usage: /allow <binary> (example: /allow rg)"
_APPROVE_COMMAND_HELP = "Usage: /approve <approval_id> [once|always]"
_DENY_COMMAND_HELP = "Usage: /deny <approval_id>"
_ALLOWLIST_BLOCKED_BINS = {
    "sh",
    "bash",
    "zsh",
    "fish",
    "cmd",
    "cmd.exe",
    "powershell",
    "pwsh",
}
_ALLOWLIST_BIN_RE = re.compile(r"^[a-z0-9._+-]+$")


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


def _is_short_agreement(reply: str) -> bool:
    """True if reply looks like a short yes/no or agreement (for reaction on user's message)."""
    if not reply or len(reply) > 80:
        return False
    t = (reply or "").strip().lower()
    # Exact or near-exact short answers
    if t in (
        "yes", "no", "yep", "nope", "ok", "okay", "sure", "done", "got it",
        "will do", "on it", "sounds good", "sounds great", "agreed", "absolutely",
        "of course", "no problem", "np", "👍", "✅", "ok!", "yes!", "no!",
    ):
        return True
    # Starts with common agreement and is short
    if len(t) <= 40 and any(t.startswith(p) for p in (
        "yes,", "no,", "ok,", "sure,", "done.", "got it.", "will do.",
        "i agree", "agreed.", "sounds good", "no problem", "of course",
    )):
        return True
    return False


async def _set_reaction(chat_id: int, message_id: int, bot, emoji: str = "👍") -> bool:
    """Set a reaction on a message (OpenClaw-style; Telegram supports 👍 👎 ❤️ etc.)."""
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji)],
        )
        return True
    except Exception as e:
        logger.debug("Could not set reaction on message: %s", e)
        return False


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
TELEGRAM_REACTION_COOLDOWN_SECONDS = 15 * 60

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
    """OpenClaw-style allowlist: numeric sender IDs only when configured."""
    settings = get_settings()
    allowed = settings.telegram_allowed_ids
    if not settings.telegram_allowlist_configured:
        return True
    # Fail closed: allowlist configured but no valid numeric IDs parsed.
    if not allowed:
        return False
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
    lock = await _get_chat_lock(chat_id)
    async with lock:
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
            if not (reply or "").strip():
                logger.info("Telegram reply suppressed (silent control token) for %s", user_id)
                return
            
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
            # React to user's message when reply is a short yes/no or agreement (OpenClaw-style)
            if _is_short_agreement(reply):
                from app.cooldowns import is_cooldown_ready, mark_cooldown_now
                from app.db import get_db

                db = get_db()
                await db.connect()
                can_react = await is_cooldown_ready(
                    db,
                    user_id,
                    "telegram_auto_reaction",
                    TELEGRAM_REACTION_COOLDOWN_SECONDS,
                )
                if can_react:
                    reacted = await _set_reaction(update.effective_chat.id, update.message.message_id, context.bot)
                    if reacted:
                        await mark_cooldown_now(db, user_id, "telegram_auto_reaction")
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

    lock = await _get_chat_lock(chat_id)
    async with lock:
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


def _exec_mode_markup(current: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(("✅ " if mode == current else "") + mode, callback_data=f"exec_mode:{mode}")
        for mode in _EXEC_MODES
    ]
    return InlineKeyboardMarkup([buttons])


def _exec_mode_text(current: str) -> str:
    return (
        "Exec mode controls shell command safety.\n\n"
        f"Current mode: {current}\n"
        "- deny: exec disabled\n"
        "- allowlist: only allowed bins run\n"
        "- full: any command allowed"
    )


def _set_exec_mode(mode: str) -> str:
    if mode not in _EXEC_MODES:
        raise ValueError("invalid mode")
    set_env_value("ASTA_EXEC_SECURITY", mode)
    return get_settings().exec_security


def _normalize_allow_bin(raw: str) -> str:
    token = (raw or "").strip().lower()
    if not token:
        return ""
    token = token.rstrip(",")
    token = token.rsplit("/", 1)[-1]
    return token


async def _add_exec_allow_bin(db, bin_name: str) -> bool:
    """Add bin to extra allowlist. Returns True if bin already existed."""
    from app.exec_tool import SYSTEM_CONFIG_EXEC_BINS_KEY

    current_extra = (await db.get_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY)) or ""
    bins = {b.strip().lower() for b in current_extra.split(",") if b.strip()}
    already = bin_name in bins
    if not already:
        bins.add(bin_name)
        await db.set_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY, ",".join(sorted(bins)))
    return already


async def allow_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return

    arg = (context.args[0] if context.args else "") or ""
    bin_name = _normalize_allow_bin(arg)
    if not bin_name:
        await update.message.reply_text(_ALLOW_COMMAND_HELP)
        return
    if not _ALLOWLIST_BIN_RE.fullmatch(bin_name):
        await update.message.reply_text(
            "Invalid binary name. Use only letters, numbers, dot, underscore, plus, or dash.\n"
            + _ALLOW_COMMAND_HELP
        )
        return
    if bin_name in _ALLOWLIST_BLOCKED_BINS:
        await update.message.reply_text(
            f"Refusing to allow '{bin_name}' for safety. "
            "Shell launchers are blocked in Telegram allowlist command."
        )
        return

    from app.db import get_db
    from app.exec_tool import get_effective_exec_bins

    db = get_db()
    await db.connect()
    already = await _add_exec_allow_bin(db, bin_name)

    effective = sorted(await get_effective_exec_bins(db, "default"))
    mode = get_settings().exec_security

    if already:
        head = f"'{bin_name}' was already in the allowlist."
    else:
        head = f"Added '{bin_name}' to allowlist."

    suffix = ""
    if mode == "deny":
        suffix = "\nExec is currently disabled. Use /exec_mode allowlist to run allowlisted commands."
    elif mode == "full":
        suffix = "\nExec is currently in full mode; allowlist is saved for when you switch back to allowlist."

    bins_text = ", ".join(effective) if effective else "(empty)"
    await update.message.reply_text(f"{head}{suffix}\n\nAllowed bins now: {bins_text}")


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    approval_id = ((context.args[0] if context.args else "") or "").strip()
    if not approval_id:
        await update.message.reply_text(_APPROVE_COMMAND_HELP)
        return
    mode_raw = ((context.args[1] if len(context.args or []) > 1 else "once") or "").strip().lower()
    if mode_raw in ("once", "allow-once"):
        mode = "once"
    elif mode_raw in ("always", "allow-always"):
        mode = "always"
    else:
        await update.message.reply_text(_APPROVE_COMMAND_HELP)
        return

    from app.db import get_db
    from app.exec_tool import get_effective_exec_bins, run_allowlisted_command

    db = get_db()
    await db.connect()
    row = await db.get_exec_approval(approval_id)
    if not row:
        await update.message.reply_text(f"Approval id not found: {approval_id}")
        return
    if str(row.get("status") or "").strip().lower() != "pending":
        await update.message.reply_text(f"Approval {approval_id} is already {row.get('status')}.")
        return

    command = str(row.get("command") or "").strip()
    binary = _normalize_allow_bin(str(row.get("binary") or ""))
    timeout_val = row.get("timeout_sec")
    timeout_sec = int(timeout_val) if isinstance(timeout_val, int) else None
    workdir_raw = row.get("workdir")
    workdir = str(workdir_raw).strip() if isinstance(workdir_raw, str) else None

    added = False
    if mode == "always" and binary:
        already = await _add_exec_allow_bin(db, binary)
        added = not already
        allowed_bins = await get_effective_exec_bins(db, "default")
    else:
        allowed_bins = {binary} if binary else set()

    stdout, stderr, ok = await run_allowlisted_command(
        command,
        allowed_bins=allowed_bins,
        timeout_seconds=timeout_sec,
        workdir=workdir,
    )
    await db.resolve_exec_approval(
        approval_id,
        status="executed" if ok else "approved",
        decision=mode,
    )

    head = (
        f"Approved {approval_id} ({mode})."
        + (f" Added '{binary}' to allowlist." if (mode == "always" and added and binary) else "")
    )
    if ok:
        out = (stdout or "").strip()
        if not out:
            out = "(no stdout)"
        msg = f"{head}\n\nCommand:\n`{command}`\n\nOutput:\n{out[:2500]}"
    else:
        err = (stderr or "Command failed.").strip()
        msg = f"{head}\n\nCommand:\n`{command}`\n\nError:\n{err[:1200]}"
    await _reply_text_safe_html(update.message, msg)


async def deny_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    approval_id = ((context.args[0] if context.args else "") or "").strip()
    if not approval_id:
        await update.message.reply_text(_DENY_COMMAND_HELP)
        return

    from app.db import get_db

    db = get_db()
    await db.connect()
    row = await db.get_exec_approval(approval_id)
    if not row:
        await update.message.reply_text(f"Approval id not found: {approval_id}")
        return
    if str(row.get("status") or "").strip().lower() != "pending":
        await update.message.reply_text(f"Approval {approval_id} is already {row.get('status')}.")
        return
    await db.resolve_exec_approval(approval_id, status="denied", decision="deny")
    await update.message.reply_text(f"Denied approval {approval_id}.")


async def approvals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return

    from app.db import get_db

    db = get_db()
    await db.connect()
    rows = await db.list_pending_exec_approvals(limit=10)
    if not rows:
        await update.message.reply_text("No pending exec approvals.")
        return

    lines = ["Pending exec approvals:"]
    for i, row in enumerate(rows, 1):
        aid = str(row.get("approval_id") or "").strip()
        binary = str(row.get("binary") or "").strip() or "unknown"
        command = str(row.get("command") or "").strip()
        short_cmd = command if len(command) <= 70 else command[:67] + "..."
        lines.append(f"{i}. {aid} [{binary}] {short_cmd}")
    lines.append("")
    lines.append("Approve: /approve <id> once|always")
    lines.append("Deny: /deny <id>")
    await update.message.reply_text("\n".join(lines))


async def allowlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return

    from app.db import get_db
    from app.exec_tool import SYSTEM_CONFIG_EXEC_BINS_KEY, get_effective_exec_bins

    db = get_db()
    await db.connect()
    mode = get_settings().exec_security
    env_bins = sorted(get_settings().exec_allowed_bins)
    extra_csv = (await db.get_system_config(SYSTEM_CONFIG_EXEC_BINS_KEY)) or ""
    extra_bins = sorted({b.strip().lower() for b in extra_csv.split(",") if b.strip()})
    effective_bins = sorted(await get_effective_exec_bins(db, "default"))

    text = (
        f"Exec mode: {mode}\n\n"
        f"Env bins (ASTA_EXEC_ALLOWED_BINS): {', '.join(env_bins) if env_bins else '(empty)'}\n"
        f"Extra bins (/allow): {', '.join(extra_bins) if extra_bins else '(empty)'}\n"
        f"Effective bins: {', '.join(effective_bins) if effective_bins else '(empty)'}"
    )
    await update.message.reply_text(text)


async def exec_mode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    current = get_settings().exec_security
    arg = ((context.args[0] if context.args else "") or "").strip().lower()
    if arg:
        if arg not in _EXEC_MODES:
            await update.message.reply_text(
                "Invalid mode. Use /exec_mode deny, /exec_mode allowlist, or /exec_mode full."
            )
            return
        try:
            current = _set_exec_mode(arg)
            await update.message.reply_text(_exec_mode_text(current), reply_markup=_exec_mode_markup(current))
        except Exception as e:
            await update.message.reply_text(f"Could not change exec mode: {str(e)[:200]}")
        return
    await update.message.reply_text(_exec_mode_text(current), reply_markup=_exec_mode_markup(current))


async def exec_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not _telegram_user_allowed(update):
        await query.answer("Unauthorized", show_alert=True)
        return
    data = (query.data or "").strip()
    mode = data.split(":", 1)[1].strip().lower() if ":" in data else ""
    if mode not in _EXEC_MODES:
        await query.answer("Invalid mode", show_alert=True)
        return
    try:
        current = _set_exec_mode(mode)
        await query.answer(f"Exec mode: {current}")
        await query.edit_message_text(_exec_mode_text(current), reply_markup=_exec_mode_markup(current))
    except Exception as e:
        await query.answer("Failed to update mode", show_alert=True)
        logger.warning("Could not set exec mode from telegram callback: %s", e)


def _thinking_markup(current: str, options: tuple[str, ...] | None = None) -> InlineKeyboardMarkup:
    levels = options or tuple(_THINK_LEVELS)
    buttons = [
        InlineKeyboardButton(("✅ " if level == current else "") + level, callback_data=f"thinking:{level}")
        for level in levels
    ]
    return InlineKeyboardMarkup([buttons])


def _supports_xhigh_thinking(provider: str | None, model: str | None) -> bool:
    model_key = (model or "").strip().lower()
    if not model_key:
        return False
    provider_key = (provider or "").strip().lower()
    if model_key in _XHIGH_MODEL_SET:
        return True
    if provider_key and f"{provider_key}/{model_key}" in _XHIGH_MODEL_SET:
        return True
    if model_key in _XHIGH_MODEL_IDS:
        return True
    if "/" in model_key and model_key.split("/", 1)[1] in _XHIGH_MODEL_IDS:
        return True
    return False


def _thinking_options(provider: str | None, model: str | None) -> tuple[str, ...]:
    base = ("off", "minimal", "low", "medium", "high")
    return base + (("xhigh",) if _supports_xhigh_thinking(provider, model) else ())


def _thinking_text(current: str, *, options: tuple[str, ...] | None = None, provider: str | None = None, model: str | None = None) -> str:
    opts = options or tuple(_THINK_LEVELS)
    opts_text = ", ".join(opts)
    model_line = ""
    if provider:
        model_label = f"{provider}/{model}" if model else f"{provider}/(default)"
        model_line = f"Active model: {model_label}\n"
    return (
        "Thinking controls how much extra verification Asta does before replying.\n\n"
        f"Current thinking level: {current}\n"
        f"Options: {opts_text}\n"
        f"{model_line}\n"
        "Use /think <level> (aliases: /thinking, /t)\n"
        "off=fastest, minimal/low=lighter checks, medium/high=deeper checks, xhigh=maximum (model-dependent)."
    )


async def _get_default_provider_model() -> tuple[str, str | None]:
    from app.db import get_db

    db = get_db()
    await db.connect()
    provider = await db.get_user_default_ai("default")
    model = await db.get_user_provider_model("default", provider)
    return provider, model


async def _set_thinking_level(level: str) -> str:
    if level not in _THINK_LEVELS:
        raise ValueError("invalid thinking level")
    from app.db import get_db

    db = get_db()
    await db.connect()
    await db.set_user_thinking_level("default", level)
    return await db.get_user_thinking_level("default")


async def _get_thinking_level() -> str:
    from app.db import get_db

    db = get_db()
    await db.connect()
    return await db.get_user_thinking_level("default")


async def thinking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    current = await _get_thinking_level()
    provider, model = await _get_default_provider_model()
    available = _thinking_options(provider, model)
    arg = ((context.args[0] if context.args else "") or "").strip().lower()
    if arg:
        if arg not in available:
            await update.message.reply_text(
                f"Unrecognized level. Valid levels for {provider}/{model or '(default)'}: {', '.join(available)}."
            )
            return
        try:
            current = await _set_thinking_level(arg)
            await update.message.reply_text(
                _thinking_text(current, options=available, provider=provider, model=model),
                reply_markup=_thinking_markup(current, options=available),
            )
        except Exception as e:
            await update.message.reply_text(f"Could not change thinking level: {str(e)[:200]}")
        return
    await update.message.reply_text(
        _thinking_text(current, options=available, provider=provider, model=model),
        reply_markup=_thinking_markup(current, options=available),
    )


async def thinking_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not _telegram_user_allowed(update):
        await query.answer("Unauthorized", show_alert=True)
        return
    data = (query.data or "").strip()
    level = data.split(":", 1)[1].strip().lower() if ":" in data else ""
    provider, model = await _get_default_provider_model()
    available = _thinking_options(provider, model)
    if level not in available:
        await query.answer("Invalid level", show_alert=True)
        return
    try:
        current = await _set_thinking_level(level)
        await query.answer(f"Thinking: {current}")
        await query.edit_message_text(
            _thinking_text(current, options=available, provider=provider, model=model),
            reply_markup=_thinking_markup(current, options=available),
        )
    except Exception as e:
        await query.answer("Failed to update thinking", show_alert=True)
        logger.warning("Could not set thinking level from telegram callback: %s", e)


def _reasoning_markup(current: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(("✅ " if mode == current else "") + mode, callback_data=f"reasoning:{mode}")
        for mode in _REASONING_MODES
    ]
    return InlineKeyboardMarkup([buttons])


def _reasoning_text(current: str) -> str:
    return (
        "Reasoning visibility controls whether <think> rationale is shown.\n\n"
        f"Current mode: {current}\n"
        "- off: hide reasoning blocks\n"
        "- on: show reasoning before final answer\n"
        "- stream: send incremental reasoning status updates before final answer"
    )


async def _set_reasoning_mode(mode: str) -> str:
    if mode not in _REASONING_MODES:
        raise ValueError("invalid reasoning mode")
    from app.db import get_db

    db = get_db()
    await db.connect()
    await db.set_user_reasoning_mode("default", mode)
    return await db.get_user_reasoning_mode("default")


async def _get_reasoning_mode() -> str:
    from app.db import get_db

    db = get_db()
    await db.connect()
    return await db.get_user_reasoning_mode("default")


async def reasoning_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return
    current = await _get_reasoning_mode()
    arg = ((context.args[0] if context.args else "") or "").strip().lower()
    if arg:
        if arg not in _REASONING_MODES:
            await update.message.reply_text(
                "Invalid mode. Use /reasoning off, /reasoning on, or /reasoning stream."
            )
            return
        try:
            current = await _set_reasoning_mode(arg)
            await update.message.reply_text(_reasoning_text(current), reply_markup=_reasoning_markup(current))
        except Exception as e:
            await update.message.reply_text(f"Could not change reasoning mode: {str(e)[:200]}")
        return
    await update.message.reply_text(_reasoning_text(current), reply_markup=_reasoning_markup(current))


async def reasoning_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not _telegram_user_allowed(update):
        await query.answer("Unauthorized", show_alert=True)
        return
    data = (query.data or "").strip()
    mode = data.split(":", 1)[1].strip().lower() if ":" in data else ""
    if mode not in _REASONING_MODES:
        await query.answer("Invalid mode", show_alert=True)
        return
    try:
        current = await _set_reasoning_mode(mode)
        await query.answer(f"Reasoning: {current}")
        await query.edit_message_text(_reasoning_text(current), reply_markup=_reasoning_markup(current))
    except Exception as e:
        await query.answer("Failed to update reasoning", show_alert=True)
        logger.warning("Could not set reasoning mode from telegram callback: %s", e)


def build_telegram_app(token: str) -> Application:
    """Build configured Application (handlers only). Caller must initialize/start in same event loop."""
    # Use AIORateLimiter to respect Telegram limits (30 msg/sec, etc.)
    # This automatically handles 429s with backoff.
    rate_limiter = AIORateLimiter(overall_max_rate=30, overall_time_period=1)
    app = Application.builder().token(token.strip()).rate_limiter(rate_limiter).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("exec_mode", exec_mode_cmd))
    app.add_handler(CommandHandler("allow", allow_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("deny", deny_cmd))
    app.add_handler(CommandHandler("approvals", approvals_cmd))
    app.add_handler(CommandHandler("allowlist", allowlist_cmd))
    app.add_handler(CommandHandler("think", thinking_cmd))
    app.add_handler(CommandHandler("thinking", thinking_cmd))
    app.add_handler(CommandHandler("t", thinking_cmd))
    app.add_handler(CommandHandler("reasoning", reasoning_cmd))
    app.add_handler(CommandHandler("subagents", subagents_cmd))
    app.add_handler(CallbackQueryHandler(exec_mode_callback, pattern=r"^exec_mode:"))
    app.add_handler(CallbackQueryHandler(thinking_callback, pattern=r"^thinking:"))
    app.add_handler(CallbackQueryHandler(reasoning_callback, pattern=r"^reasoning:"))
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

    lock = await _get_chat_lock(chat_id)
    async with lock:
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
            if not (reply or "").strip():
                logger.info("Telegram photo reply suppressed (silent control token) for %s", user_id)
                return
            
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

    def _pct(v: float | int) -> str:
        try:
            f = float(v)
        except Exception:
            return "?"
        if abs(f - round(f)) < 0.05:
            return f"{int(round(f))}%"
        return f"{f:.1f}%"

    def _gb(v: float | int) -> str:
        try:
            return f"{float(v):.2f}".rstrip("0").rstrip(".")
        except Exception:
            return "?"

    def _level(pct: float | int) -> tuple[str, str]:
        try:
            f = float(pct)
        except Exception:
            return ("⚪", "unknown")
        if f >= 85:
            return ("🔴", "busy")
        if f >= 65:
            return ("🟡", "a bit busy")
        return ("🟢", "good")

    if ss.get("ok"):
        cpu_pct = float(ss.get("cpu_percent", 0) or 0)
        ram = ss.get("ram", {}) or {}
        disk = ss.get("disk", {}) or {}
        ram_pct = float(ram.get("percent", 0) or 0)
        disk_pct = float(disk.get("percent", 0) or 0)
        cpu_icon, cpu_level = _level(cpu_pct)
        ram_icon, ram_level = _level(ram_pct)
        disk_icon, disk_level = _level(disk_pct)
        version = html.escape(str(ss.get("version", "?")))
        uptime = html.escape(str(ss.get("uptime_str", "?")))
        overall = "Good"
        if cpu_pct >= 85 or ram_pct >= 85 or disk_pct >= 90:
            overall = "Busy"
        elif cpu_pct >= 65 or ram_pct >= 65 or disk_pct >= 80:
            overall = "OK"

        text = (
            f"<b>🖥️ Asta Server</b> <code>v{version}</code>\n"
            f"<b>Status</b> ✅ Online ({overall})\n\n"
            f"<b>System load</b> {cpu_icon} {_pct(cpu_pct)} ({cpu_level})\n"
            f"<b>Memory used</b> {ram_icon} {_gb(ram.get('used_gb', 0))} / {_gb(ram.get('total_gb', 0))} GB ({ram_level})\n"
            f"<b>Storage used</b> {disk_icon} {_gb(disk.get('used_gb', 0))} / {_gb(disk.get('total_gb', 0))} GB ({disk_level})\n\n"
            f"<b>Running for</b> {uptime}"
        )
    else:
        err = html.escape(str(ss.get("error", "Unknown error")))
        text = f"<b>⚠️ Status Check Failed</b>\n<code>{err}</code>"

    await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True)


async def subagents_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /subagents command by delegating to handler's deterministic subagent command path."""
    if not update.message:
        return
    if not _telegram_user_allowed(update):
        await update.message.reply_text("You're not authorized to use this bot.")
        return

    user_id = "default"
    chat_id = update.effective_chat.id if update.effective_chat else 0
    lock = await _get_chat_lock(chat_id)
    async with lock:
        chat_id_str = str(chat_id)
        suffix = " ".join(context.args or []).strip()
        text = "/subagents" + (f" {suffix}" if suffix else "")
        try:
            await update.message.chat.send_action("typing")
            reply = await handle_message(
                user_id,
                "telegram",
                text,
                provider_name="default",
                channel_target=chat_id_str,
            )
            out = (reply or "").strip()[:TELEGRAM_MAX_MESSAGE_LENGTH] or "No response."
            await _reply_text_safe_html(update.message, out)
        except Exception as e:
            logger.exception("Telegram /subagents handler error")
            await update.message.reply_text(f"Error: {str(e)[:500]}")


async def start_telegram_bot_in_loop(app: Application) -> None:
    """Initialize and start polling + processor. Run inside FastAPI lifespan (same event loop)."""
    await app.initialize()
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Start Asta"),
            BotCommand("status", "Show server status"),
            BotCommand("exec_mode", "Set exec security mode (deny/allowlist/full)"),
            BotCommand("allow", "Allow binary in exec allowlist"),
            BotCommand("approve", "Approve pending exec command"),
            BotCommand("deny", "Deny pending exec command"),
            BotCommand("approvals", "List pending exec approvals"),
            BotCommand("allowlist", "Show allowed exec binaries"),
            BotCommand("think", "Set thinking level (off/minimal/low/medium/high/xhigh)"),
            BotCommand("reasoning", "Set reasoning visibility (off/on/stream)"),
            BotCommand("subagents", "Manage subagents (list/spawn/info/send/stop)"),
        ])
    except Exception as e:
        logger.warning("Could not register Telegram bot commands: %s", e)
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await app.start()
    invalid = sorted(get_settings().telegram_allowlist_invalid)
    if invalid:
        logger.warning(
            "ASTA_TELEGRAM_ALLOWED_IDS contains non-numeric entries (ignored): %s",
            ", ".join(invalid[:5]) + (f" (+{len(invalid) - 5} more)" if len(invalid) > 5 else ""),
        )
    logger.info("Telegram bot polling started (same loop as FastAPI)")
