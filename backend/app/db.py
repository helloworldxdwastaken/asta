"""SQLite persistence: conversations, messages, tasks."""
from __future__ import annotations
import aiosqlite
import os
from pathlib import Path
from typing import Any

DB_PATH = os.environ.get("ASTA_DB_PATH", str(Path(__file__).resolve().parent.parent / "asta.db"))


class Db:
    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None
        import logging
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(DB_PATH)
        self._conn.row_factory = aiosqlite.Row
        await self._init_schema()

    async def _init_schema(self) -> None:
        if not self._conn:
            return
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider_used TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL,
                run_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                channel_target TEXT NOT NULL,
                message TEXT NOT NULL,
                run_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                mood TEXT NOT NULL DEFAULT 'normal',
                default_ai_provider TEXT NOT NULL DEFAULT 'groq',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key_name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS skill_toggles (
                user_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, skill_id)
            );
            CREATE TABLE IF NOT EXISTS provider_models (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
            CREATE TABLE IF NOT EXISTS user_location (
                user_id TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS spotify_user_tokens (
                user_id TEXT PRIMARY KEY,
                refresh_token TEXT NOT NULL,
                access_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_spotify_play (
                user_id TEXT PRIMARY KEY,
                track_uri TEXT NOT NULL,
                devices_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS saved_audio_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                title TEXT NOT NULL,
                transcript TEXT NOT NULL,
                formatted TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_learn_about (
                user_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_saved_audio_notes_user ON saved_audio_notes(user_id);
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_at);
            CREATE INDEX IF NOT EXISTS idx_reminders_run ON reminders(run_at);
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        await self._conn.commit()
        # Check if column exists before adding
        cursor = await self._conn.execute("PRAGMA table_info(user_settings)")
        columns = [row["name"] for row in await cursor.fetchall()]
        if "default_ai_provider" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN default_ai_provider TEXT NOT NULL DEFAULT 'groq'"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add default_ai_provider column: %s", e)

        if "pending_location_request" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN pending_location_request TEXT"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add pending_location_request column: %s", e)

        if "fallback_providers" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN fallback_providers TEXT DEFAULT ''"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add fallback_providers column: %s", e)

    async def get_or_create_conversation(self, user_id: str, channel: str) -> str:
        if not self._conn:
            await self.connect()
        cid = f"{user_id}:{channel}"
        await self._conn.execute(
            "INSERT OR IGNORE INTO conversations (id, user_id, channel, created_at) VALUES (?, ?, ?, datetime('now'))",
            (cid, user_id, channel),
        )
        await self._conn.commit()
        return cid

    async def add_message(self, conversation_id: str, role: str, content: str, provider_used: str | None = None) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, provider_used, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (conversation_id, role, content, provider_used),
        )
        await self._conn.commit()

    async def get_recent_messages(self, conversation_id: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = await cursor.fetchall()
        out = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        return out

    async def add_task(self, user_id: str, type: str, payload: dict, status: str = "pending", run_at: str | None = None) -> int:
        if not self._conn:
            await self.connect()
        import json
        await self._conn.execute(
            "INSERT INTO tasks (user_id, type, payload, status, run_at, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (user_id, type, json.dumps(payload), status, run_at),
        )
        await self._conn.commit()
        cursor = await self._conn.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_user_mood(self, user_id: str) -> str:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT mood FROM user_settings WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["mood"] if row else "normal"

    async def set_user_mood(self, user_id: str, mood: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at) VALUES (?, ?, 'groq', datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET mood = ?, updated_at = datetime('now')""",
            (user_id, mood, mood),
        )
        await self._conn.commit()

    async def get_user_default_ai(self, user_id: str) -> str:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT default_ai_provider FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return (row["default_ai_provider"] or "groq") if row else "groq"
        except Exception as e:
            self.logger.exception("Failed to get user default AI: %s", e)
            return "groq"

    async def set_user_default_ai(self, user_id: str, provider: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at) VALUES (?, 'normal', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET default_ai_provider = ?, updated_at = datetime('now')""",
            (user_id, provider, provider),
        )
        await self._conn.commit()

    async def get_user_location(self, user_id: str) -> dict[str, Any] | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT location_name, latitude, longitude FROM user_location WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "location_name": row["location_name"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }

    async def set_user_location(self, user_id: str, location_name: str, latitude: float, longitude: float) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO user_location (user_id, location_name, latitude, longitude, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET location_name = ?, latitude = ?, longitude = ?, updated_at = datetime('now')""",
            (user_id, location_name, latitude, longitude, location_name, latitude, longitude),
        )
        await self._conn.commit()

    async def get_skill_enabled(self, user_id: str, skill_id: str) -> bool:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT enabled FROM skill_toggles WHERE user_id = ? AND skill_id = ?",
                (user_id, skill_id),
            )
            row = await cursor.fetchone()
            # No row = user never toggled this skill → default ON so new skills (time_weather, google_search) work
            return bool(row["enabled"]) if row else True
        except Exception as e:
            self.logger.exception("Failed to get skill enabled: %s", e)
            return True  # default on

    async def get_all_skill_toggles(self, user_id: str) -> dict[str, bool]:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT skill_id, enabled FROM skill_toggles WHERE user_id = ?",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return {r["skill_id"]: bool(r["enabled"]) for r in rows}
        except Exception as e:
            self.logger.exception("Failed to get all skill toggles: %s", e)
            return {}

    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO skill_toggles (user_id, skill_id, enabled) VALUES (?, ?, ?)
               ON CONFLICT(user_id, skill_id) DO UPDATE SET enabled = ?""",
            (user_id, skill_id, 1 if enabled else 0, 1 if enabled else 0),
        )
        await self._conn.commit()

    async def get_user_provider_model(self, user_id: str, provider: str) -> str | None:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT model FROM provider_models WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )
            row = await cursor.fetchone()
            return row["model"] if row and row["model"] else None
        except Exception as e:
            self.logger.exception("Failed to get user provider model: %s", e)
            return None

    async def get_all_provider_models(self, user_id: str) -> dict[str, str]:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT provider, model FROM provider_models WHERE user_id = ?",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return {r["provider"]: r["model"] for r in rows}
        except Exception as e:
            self.logger.exception("Failed to get all provider models: %s", e)
            return {}

    async def set_user_provider_model(self, user_id: str, provider: str, model: str) -> None:
        if not self._conn:
            await self.connect()
        if not model or not model.strip():
            await self._conn.execute(
                "DELETE FROM provider_models WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )
        else:
            await self._conn.execute(
                """INSERT INTO provider_models (user_id, provider, model) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, provider) DO UPDATE SET model = ?""",
                (user_id, provider, model.strip(), model.strip()),
            )
        await self._conn.commit()

    async def add_reminder(
        self, user_id: str, channel: str, channel_target: str, message: str, run_at: str
    ) -> int:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO reminders (user_id, channel, channel_target, message, run_at, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', datetime('now'))""",
            (user_id, channel, channel_target, message, run_at),
        )
        await self._conn.commit()
        cursor = await self._conn.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_pending_reminders_due(self, now_iso: str) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT id, user_id, channel, channel_target, message FROM reminders WHERE status = 'pending' AND run_at <= ?",
            (now_iso,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_pending_reminders(self) -> list[dict[str, Any]]:
        """All reminders with status=pending (for re-scheduling on startup)."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT id, run_at FROM reminders WHERE status = 'pending' ORDER BY run_at ASC",
            (),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def mark_reminder_sent(self, reminder_id: int) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (reminder_id,))
        await self._conn.commit()

    async def get_notifications(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """SELECT id, message, run_at, status, channel, created_at FROM reminders
               WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_pending_reminders_for_user(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Pending reminders for context (message, run_at)."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """SELECT message, run_at FROM reminders WHERE user_id = ? AND status = 'pending'
               ORDER BY run_at ASC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def delete_reminder(self, reminder_id: int) -> bool:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def set_pending_learn_about(self, user_id: str, topic: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO pending_learn_about (user_id, topic, created_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET topic = ?, created_at = datetime('now')""",
            (user_id, topic, topic),
        )
        await self._conn.commit()

    async def get_pending_learn_about(self, user_id: str, max_age_minutes: int = 10) -> dict[str, Any] | None:
        """Return {topic} if user has a recent pending 'learn about X' (no duration). None if expired or missing."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT topic FROM pending_learn_about WHERE user_id = ? AND datetime(created_at) >= datetime('now', ?)",
            (user_id, f"-{max_age_minutes} minutes"),
        )
        row = await cursor.fetchone()
        return {"topic": row["topic"]} if row else None

    async def clear_pending_learn_about(self, user_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute("DELETE FROM pending_learn_about WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def get_stored_api_key(self, key_name: str) -> str | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT value FROM api_keys WHERE key_name = ?", (key_name,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_stored_api_key(self, key_name: str, value: str) -> None:
        if not self._conn:
            await self.connect()
        if not value.strip():
            await self._conn.execute("DELETE FROM api_keys WHERE key_name = ?", (key_name,))
        else:
            await self._conn.execute(
                """INSERT INTO api_keys (key_name, value, updated_at) VALUES (?, ?, datetime('now'))
                   ON CONFLICT(key_name) DO UPDATE SET value = ?, updated_at = datetime('now')""",
                (key_name, value.strip(), value.strip()),
            )
        await self._conn.commit()

    async def get_api_keys_status(self) -> dict[str, bool]:
        """Return which API keys are set (true/false), no values."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute("SELECT key_name FROM api_keys")
        rows = await cursor.fetchall()
        return {r["key_name"]: True for r in rows}

    # Spotify user OAuth tokens (for playback)
    async def get_spotify_tokens(self, user_id: str) -> dict[str, Any] | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT refresh_token, access_token, expires_at FROM spotify_user_tokens WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_spotify_tokens(self, user_id: str, refresh_token: str, access_token: str, expires_at: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO spotify_user_tokens (user_id, refresh_token, access_token, expires_at, updated_at)
               VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(user_id) DO UPDATE SET
               refresh_token = ?, access_token = ?, expires_at = ?, updated_at = datetime('now')""",
            (user_id, refresh_token, access_token, expires_at, refresh_token, access_token, expires_at),
        )
        await self._conn.commit()

    async def clear_spotify_tokens(self, user_id: str) -> None:
        """Remove stored Spotify OAuth tokens (e.g. after invalid_grant)."""
        if not self._conn:
            await self.connect()
        await self._conn.execute("DELETE FROM spotify_user_tokens WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def get_pending_spotify_play(self, user_id: str) -> dict[str, Any] | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT track_uri, devices_json FROM pending_spotify_play WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_pending_spotify_play(self, user_id: str, track_uri: str, devices_json: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO pending_spotify_play (user_id, track_uri, devices_json, created_at)
               VALUES (?, ?, ?, datetime('now')) ON CONFLICT(user_id) DO UPDATE SET
               track_uri = ?, devices_json = ?, created_at = datetime('now')""",
            (user_id, track_uri, devices_json, track_uri, devices_json),
        )
        await self._conn.commit()

    async def clear_pending_spotify_play(self, user_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute("DELETE FROM pending_spotify_play WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def save_audio_note(self, user_id: str, title: str, transcript: str, formatted: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            "INSERT INTO saved_audio_notes (user_id, created_at, title, transcript, formatted) VALUES (?, datetime('now'), ?, ?, ?)",
            (user_id, title, transcript, formatted),
        )
        await self._conn.commit()

    async def get_recent_audio_notes(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT id, created_at, title, transcript, formatted FROM saved_audio_notes WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def set_pending_location_request(self, user_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO user_settings (user_id, mood, default_ai_provider, pending_location_request, updated_at)
               VALUES (?, 'normal', 'groq', datetime('now'), datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET pending_location_request = datetime('now'), updated_at = datetime('now')""",
            (user_id,),
        )
        await self._conn.commit()

    async def get_pending_location_request(self, user_id: str, max_age_minutes: int = 5) -> bool:
        """Return True if we asked for location recently."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT pending_location_request FROM user_settings WHERE user_id = ? AND datetime(pending_location_request) >= datetime('now', ?)",
            (user_id, f"-{max_age_minutes} minutes"),
        )
        row = await cursor.fetchone()
        return bool(row["pending_location_request"]) if row else False

    async def clear_pending_location_request(self, user_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            "UPDATE user_settings SET pending_location_request = NULL WHERE user_id = ?",
            (user_id,),
        )
        await self._conn.commit()

    async def get_user_fallback_providers(self, user_id: str) -> str:
        """Get comma-separated fallback provider names (e.g. 'google,openai'). Empty if not set."""
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT fallback_providers FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return (row["fallback_providers"] or "") if row else ""
        except Exception:
            return ""

    async def set_user_fallback_providers(self, user_id: str, providers_csv: str) -> None:
        """Set fallback providers (comma-separated names, e.g. 'google,openai')."""
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO user_settings (user_id, mood, default_ai_provider, fallback_providers, updated_at)
               VALUES (?, 'normal', 'groq', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET fallback_providers = ?, updated_at = datetime('now')""",
            (user_id, providers_csv, providers_csv),
        )
        await self._conn.commit()


    async def get_system_config(self, key: str) -> str | None:
        """Get a global system setting."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT value FROM system_config WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_system_config(self, key: str, value: str) -> None:
        """Set a global system setting."""
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')""",
            (key, value, value),
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None


_db: Db | None = None


def get_db() -> Db:
    global _db
    if _db is None:
        _db = Db()
    return _db
