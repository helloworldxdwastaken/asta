"""SQLite persistence: conversations, messages, tasks."""
from __future__ import annotations
import aiosqlite
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.provider_flow import DEFAULT_MAIN_PROVIDER, MAIN_PROVIDER_CHAIN

DB_PATH = os.environ.get("ASTA_DB_PATH", str(Path(__file__).resolve().parent.parent / "asta.db"))
THINK_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh")
FINAL_MODES = ("off", "strict")

# One-shot reminders are stored as cron jobs with an "@at <ISO-UTC>" expression.
ONE_SHOT_CRON_PREFIX = "@at "
ONE_SHOT_REMINDER_NAME_PREFIX = "__reminder__:"
ONE_SHOT_REMINDER_ID_OFFSET = 1_000_000_000


def normalize_iso_utc(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return (value or "").strip()


def is_one_shot_cron_expr(expr: str) -> bool:
    return (expr or "").strip().lower().startswith(ONE_SHOT_CRON_PREFIX)


def run_at_to_one_shot_cron_expr(run_at_iso: str) -> str:
    return f"{ONE_SHOT_CRON_PREFIX}{normalize_iso_utc(run_at_iso)}"


def one_shot_cron_expr_to_run_at(expr: str) -> str | None:
    raw = (expr or "").strip()
    if not is_one_shot_cron_expr(raw):
        return None
    run_at_raw = raw[len(ONE_SHOT_CRON_PREFIX):].strip()
    if not run_at_raw:
        return None
    return normalize_iso_utc(run_at_raw)


def encode_one_shot_reminder_id(cron_job_id: int) -> int:
    return ONE_SHOT_REMINDER_ID_OFFSET + int(cron_job_id)


def decode_one_shot_reminder_id(reminder_id: int) -> int | None:
    try:
        rid = int(reminder_id)
    except Exception:
        return None
    if rid >= ONE_SHOT_REMINDER_ID_OFFSET:
        return rid - ONE_SHOT_REMINDER_ID_OFFSET
    return None


def validate_cron_expression(expr: str, tz: str | None = None) -> tuple[bool, str]:
    """Validate cron expression syntax.

    Returns (True, "") if valid, or (False, error_message) if invalid.
    """
    try:
        # Check if one-shot cron (@at format)
        if is_one_shot_cron_expr(expr):
            run_at = one_shot_cron_expr_to_run_at(expr)
            if not run_at:
                return False, "Invalid @at timestamp format"
            return True, ""

        # Validate 5-field cron
        parts = expr.split()
        if len(parts) != 5:
            return False, f"Expected 5 fields, got {len(parts)}"

        # Basic field validation (can be enhanced)
        for i, part in enumerate(parts):
            if not part or part.isspace():
                return False, f"Field {i+1} is empty"

        return True, ""
    except Exception as e:
        return False, str(e)


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
        await self._conn.executescript(f"""
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
                default_ai_provider TEXT NOT NULL DEFAULT '{DEFAULT_MAIN_PROVIDER}',
                thinking_level TEXT NOT NULL DEFAULT 'off',
                reasoning_mode TEXT NOT NULL DEFAULT 'off',
                final_mode TEXT NOT NULL DEFAULT 'off',
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
            CREATE TABLE IF NOT EXISTS provider_runtime_state (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                auto_disabled INTEGER NOT NULL DEFAULT 0,
                disabled_reason TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
            CREATE INDEX IF NOT EXISTS idx_provider_runtime_state_user
                ON provider_runtime_state(user_id, provider);
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
            CREATE TABLE IF NOT EXISTS spotify_retry_request (
                user_id TEXT PRIMARY KEY,
                play_query TEXT NOT NULL,
                track_uri TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS exec_approvals (
                approval_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                channel_target TEXT,
                command TEXT NOT NULL,
                binary TEXT NOT NULL,
                timeout_sec INTEGER,
                workdir TEXT,
                background INTEGER NOT NULL DEFAULT 0,
                pty INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                decision TEXT,
                resolved_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_exec_approvals_pending_created
                ON exec_approvals(status, created_at DESC);
            CREATE TABLE IF NOT EXISTS allowed_paths (
                user_id TEXT NOT NULL,
                path TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (user_id, path)
            );
            CREATE TABLE IF NOT EXISTS cron_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                cron_expr TEXT NOT NULL,
                tz TEXT,
                message TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'web',
                channel_target TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                payload_kind TEXT NOT NULL DEFAULT 'agentturn',
                tlg_call INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE (user_id, name)
            );
            CREATE INDEX IF NOT EXISTS idx_cron_jobs_enabled ON cron_jobs(user_id, enabled);
            CREATE TABLE IF NOT EXISTS cron_job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cron_job_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'schedule',
                run_mode TEXT NOT NULL DEFAULT 'due',
                status TEXT NOT NULL,
                output TEXT,
                error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cron_job_runs_job_created
                ON cron_job_runs(cron_job_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_cron_job_runs_user_created
                ON cron_job_runs(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS subagent_runs (
                run_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                parent_conversation_id TEXT NOT NULL,
                child_conversation_id TEXT NOT NULL,
                task TEXT NOT NULL,
                label TEXT,
                provider_name TEXT,
                model_override TEXT,
                thinking_override TEXT,
                run_timeout_seconds INTEGER NOT NULL DEFAULT 0,
                channel TEXT NOT NULL,
                channel_target TEXT,
                cleanup TEXT NOT NULL DEFAULT 'keep',
                status TEXT NOT NULL,
                result_text TEXT,
                error_text TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                archived_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_subagent_parent_created ON subagent_runs(parent_conversation_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_subagent_status ON subagent_runs(status, created_at DESC);
        """)
        await self._conn.commit()
        # Migrations
        cursor = await self._conn.execute("PRAGMA table_info(cron_jobs)")
        cron_cols = [row["name"] for row in await cursor.fetchall()]
        if "payload_kind" not in cron_cols:
            try:
                await self._conn.execute(
                    "ALTER TABLE cron_jobs ADD COLUMN payload_kind TEXT NOT NULL DEFAULT 'agentturn'"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add payload_kind column to cron_jobs: %s", e)

        if "tlg_call" not in cron_cols:
            try:
                await self._conn.execute(
                    "ALTER TABLE cron_jobs ADD COLUMN tlg_call INTEGER NOT NULL DEFAULT 0"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add tlg_call column to cron_jobs: %s", e)

        # Check if column exists before adding
        cursor = await self._conn.execute("PRAGMA table_info(user_settings)")
        columns = [row["name"] for row in await cursor.fetchall()]
        if "default_ai_provider" not in columns:
            try:
                await self._conn.execute(
                    f"ALTER TABLE user_settings ADD COLUMN default_ai_provider TEXT NOT NULL DEFAULT '{DEFAULT_MAIN_PROVIDER}'"
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
        if "thinking_level" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN thinking_level TEXT NOT NULL DEFAULT 'off'"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add thinking_level column: %s", e)
        if "reasoning_mode" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN reasoning_mode TEXT NOT NULL DEFAULT 'off'"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add reasoning_mode column: %s", e)
        if "final_mode" not in columns:
            try:
                await self._conn.execute(
                    "ALTER TABLE user_settings ADD COLUMN final_mode TEXT NOT NULL DEFAULT 'off'"
                )
                await self._conn.commit()
            except Exception as e:
                self.logger.exception("Failed to add final_mode column: %s", e)
        # Subagent runs table migrations (for older installs).
        try:
            cursor = await self._conn.execute("PRAGMA table_info(subagent_runs)")
            sub_cols = [row["name"] for row in await cursor.fetchall()]
            migrations = [
                ("model_override", "ALTER TABLE subagent_runs ADD COLUMN model_override TEXT"),
                ("thinking_override", "ALTER TABLE subagent_runs ADD COLUMN thinking_override TEXT"),
                (
                    "run_timeout_seconds",
                    "ALTER TABLE subagent_runs ADD COLUMN run_timeout_seconds INTEGER NOT NULL DEFAULT 0",
                ),
                ("archived_at", "ALTER TABLE subagent_runs ADD COLUMN archived_at TEXT"),
            ]
            for col, sql in migrations:
                if col in sub_cols:
                    continue
                try:
                    await self._conn.execute(sql)
                    await self._conn.commit()
                except Exception as e:
                    self.logger.exception("Failed to add subagent_runs.%s column: %s", col, e)
        except Exception as e:
            self.logger.debug("subagent_runs table migration check skipped: %s", e)

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

    async def create_new_conversation(self, user_id: str, channel: str) -> str:
        """Create a brand-new conversation with a unique ID."""
        if not self._conn:
            await self.connect()
        from uuid import uuid4
        cid = f"{user_id}:{channel}:{uuid4().hex[:8]}"
        await self._conn.execute(
            "INSERT INTO conversations (id, user_id, channel, created_at) VALUES (?, ?, ?, datetime('now'))",
            (cid, user_id, channel),
        )
        await self._conn.commit()
        return cid

    async def list_conversations(self, user_id: str, channel: str = "web", limit: int = 50) -> list[dict[str, Any]]:
        """List conversations ordered by most recent activity, with title from first user message."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """
            SELECT
                c.id,
                c.created_at,
                (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user' ORDER BY id ASC LIMIT 1) AS title,
                (SELECT created_at FROM messages WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1) AS last_active
            FROM conversations c
            WHERE c.user_id = ? AND c.channel = ?
              AND EXISTS (SELECT 1 FROM messages WHERE conversation_id = c.id)
            ORDER BY COALESCE(
                (SELECT created_at FROM messages WHERE conversation_id = c.id ORDER BY id DESC LIMIT 1),
                c.created_at
            ) DESC
            LIMIT ?
            """,
            (user_id, channel, limit),
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            title = r["title"] or "New conversation"
            if len(title) > 80:
                title = title[:80] + "…"
            result.append({
                "id": r["id"],
                "title": title,
                "created_at": r["created_at"],
                "last_active": r["last_active"] or r["created_at"],
            })
        return result

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

    async def delete_conversation(self, conversation_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        await self._conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await self._conn.commit()

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

    async def add_subagent_run(
        self,
        *,
        run_id: str,
        user_id: str,
        parent_conversation_id: str,
        child_conversation_id: str,
        task: str,
        label: str | None,
        provider_name: str | None,
        channel: str,
        channel_target: str,
        cleanup: str,
        status: str,
        model_override: str | None = None,
        thinking_override: str | None = None,
        run_timeout_seconds: int = 0,
    ) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT OR REPLACE INTO subagent_runs
               (run_id, user_id, parent_conversation_id, child_conversation_id, task, label, provider_name,
                model_override, thinking_override, run_timeout_seconds, channel, channel_target,
                cleanup, status, created_at, started_at, ended_at, archived_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), NULL, NULL)""",
            (
                run_id,
                user_id,
                parent_conversation_id,
                child_conversation_id,
                task,
                (label or "").strip() or None,
                (provider_name or "").strip() or None,
                (model_override or "").strip() or None,
                (thinking_override or "").strip().lower() or None,
                max(0, int(run_timeout_seconds or 0)),
                channel,
                channel_target or "",
                cleanup,
                status,
            ),
        )
        await self._conn.commit()

    async def update_subagent_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        result_text: str | None = None,
        error_text: str | None = None,
        ended: bool = False,
        archived: bool = False,
    ) -> None:
        if not self._conn:
            await self.connect()
        fields: list[str] = []
        params: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if result_text is not None:
            fields.append("result_text = ?")
            params.append(result_text)
        if error_text is not None:
            fields.append("error_text = ?")
            params.append(error_text)
        if ended:
            fields.append("ended_at = datetime('now')")
        if archived:
            fields.append("archived_at = datetime('now')")
        if not fields:
            return
        params.append(run_id)
        await self._conn.execute(
            f"UPDATE subagent_runs SET {', '.join(fields)} WHERE run_id = ?",
            tuple(params),
        )
        await self._conn.commit()

    async def get_subagent_run(self, run_id: str) -> dict[str, Any] | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT * FROM subagent_runs WHERE run_id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_subagent_runs(self, parent_conversation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """SELECT * FROM subagent_runs
               WHERE parent_conversation_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (parent_conversation_id, max(1, min(int(limit), 200))),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_subagent_runs_by_status(self, statuses: list[str], limit: int = 200) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        normalized = [s.strip().lower() for s in statuses if (s or "").strip()]
        if not normalized:
            return []
        placeholders = ",".join("?" for _ in normalized)
        cursor = await self._conn.execute(
            f"""SELECT * FROM subagent_runs
                WHERE lower(status) IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ?""",
            tuple(normalized + [max(1, min(int(limit), 2000))]),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def mark_running_subagent_runs_interrupted(self) -> int:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """UPDATE subagent_runs
               SET status = 'interrupted',
                   error_text = COALESCE(error_text, 'Asta restarted before this subagent finished.'),
                   ended_at = datetime('now')
               WHERE lower(status) = 'running'"""
        )
        await self._conn.commit()
        return int(cursor.rowcount or 0)

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
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at) VALUES (?, ?, '{DEFAULT_MAIN_PROVIDER}', datetime('now'))
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
            return (row["default_ai_provider"] or DEFAULT_MAIN_PROVIDER) if row else DEFAULT_MAIN_PROVIDER
        except Exception as e:
            self.logger.exception("Failed to get user default AI: %s", e)
            return DEFAULT_MAIN_PROVIDER

    async def set_user_default_ai(self, user_id: str, provider: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, updated_at) VALUES (?, 'normal', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET default_ai_provider = ?, updated_at = datetime('now')""",
            (user_id, provider, provider),
        )
        await self._conn.commit()

    async def get_user_thinking_level(self, user_id: str) -> str:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT thinking_level FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return "off"
            level = (row["thinking_level"] or "off").strip().lower()
            if level not in THINK_LEVELS:
                return "off"
            return level
        except Exception as e:
            self.logger.exception("Failed to get user thinking level: %s", e)
            return "off"

    async def set_user_thinking_level(self, user_id: str, level: str) -> None:
        if not self._conn:
            await self.connect()
        normalized = (level or "off").strip().lower()
        if normalized not in THINK_LEVELS:
            normalized = "off"
        await self._conn.execute(
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, thinking_level, updated_at)
               VALUES (?, 'normal', '{DEFAULT_MAIN_PROVIDER}', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET thinking_level = ?, updated_at = datetime('now')""",
            (user_id, normalized, normalized),
        )
        await self._conn.commit()

    async def get_user_reasoning_mode(self, user_id: str) -> str:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT reasoning_mode FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return "off"
            mode = (row["reasoning_mode"] or "off").strip().lower()
            if mode not in ("off", "on", "stream"):
                return "off"
            return mode
        except Exception as e:
            self.logger.exception("Failed to get user reasoning mode: %s", e)
            return "off"

    async def set_user_reasoning_mode(self, user_id: str, mode: str) -> None:
        if not self._conn:
            await self.connect()
        normalized = (mode or "off").strip().lower()
        if normalized not in ("off", "on", "stream"):
            normalized = "off"
        await self._conn.execute(
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, reasoning_mode, updated_at)
               VALUES (?, 'normal', '{DEFAULT_MAIN_PROVIDER}', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET reasoning_mode = ?, updated_at = datetime('now')""",
            (user_id, normalized, normalized),
        )
        await self._conn.commit()

    async def get_user_final_mode(self, user_id: str) -> str:
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT final_mode FROM user_settings WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return "off"
            mode = (row["final_mode"] or "off").strip().lower()
            if mode not in FINAL_MODES:
                return "off"
            return mode
        except Exception as e:
            self.logger.exception("Failed to get user final mode: %s", e)
            return "off"

    async def set_user_final_mode(self, user_id: str, mode: str) -> None:
        if not self._conn:
            await self.connect()
        normalized = (mode or "off").strip().lower()
        if normalized not in FINAL_MODES:
            normalized = "off"
        await self._conn.execute(
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, final_mode, updated_at)
               VALUES (?, 'normal', '{DEFAULT_MAIN_PROVIDER}', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET final_mode = ?, updated_at = datetime('now')""",
            (user_id, normalized, normalized),
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

    async def get_allowed_paths(self, user_id: str) -> list[str]:
        """Paths the user has allowed for file access (OpenClaw-style; merged with env ASTA_ALLOWED_PATHS in files router)."""
        if not self._conn:
            await self.connect()
        try:
            cursor = await self._conn.execute(
                "SELECT path FROM allowed_paths WHERE user_id = ? ORDER BY added_at",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [r["path"] for r in rows]
        except Exception as e:
            self.logger.exception("Failed to get allowed paths: %s", e)
            return []

    async def add_allowed_path(self, user_id: str, path: str) -> None:
        """Add a path to the user's allowlist (e.g. after 'request access'). Path should be absolute and resolved."""
        if not self._conn:
            await self.connect()
        path = str(Path(path).resolve()) if path.strip() else ""
        if not path:
            return
        await self._conn.execute(
            "INSERT OR IGNORE INTO allowed_paths (user_id, path, added_at) VALUES (?, ?, datetime('now'))",
            (user_id, path),
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
        self, user_id: str, channel: str, channel_target: str, message: str, run_at: str, tlg_call: bool = False
    ) -> int:
        if not self._conn:
            await self.connect()
        run_at_norm = normalize_iso_utc(run_at)
        # OpenClaw-style internals: store one-shot reminders as cron jobs.
        cron_expr = run_at_to_one_shot_cron_expr(run_at_norm)
        name = f"{ONE_SHOT_REMINDER_NAME_PREFIX}{uuid4().hex}"
        cron_id = await self.add_cron_job(
            user_id,
            name,
            cron_expr,
            message or "Reminder",
            tz=None,
            channel=channel or "web",
            channel_target=channel_target or "",
            tlg_call=tlg_call,
        )
        return encode_one_shot_reminder_id(cron_id)

    async def get_pending_reminders_due(self, now_iso: str) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        now_norm = normalize_iso_utc(now_iso)
        pending_rows: list[dict[str, Any]] = []
        cursor = await self._conn.execute(
            """SELECT id, user_id, channel, channel_target, message, cron_expr
               FROM cron_jobs
               WHERE enabled = 1 AND lower(trim(cron_expr)) LIKE '@at %'"""
        )
        for row in await cursor.fetchall():
            run_at = one_shot_cron_expr_to_run_at(row["cron_expr"] or "")
            if run_at and run_at <= now_norm:
                pending_rows.append(
                    {
                        "id": encode_one_shot_reminder_id(int(row["id"])),
                        "user_id": row["user_id"],
                        "channel": row["channel"],
                        "channel_target": row["channel_target"],
                        "message": row["message"],
                    }
                )
        # Legacy fallback (pre-migration rows).
        cursor = await self._conn.execute(
            "SELECT id, user_id, channel, channel_target, message FROM reminders WHERE status = 'pending' AND run_at <= ?",
            (now_norm,),
        )
        rows = await cursor.fetchall()
        pending_rows.extend(dict(r) for r in rows)
        return pending_rows

    async def get_all_pending_reminders(self) -> list[dict[str, Any]]:
        """All pending reminders (one-shot cron + legacy rows)."""
        if not self._conn:
            await self.connect()
        out: list[dict[str, Any]] = []
        cursor = await self._conn.execute(
            """SELECT id, cron_expr FROM cron_jobs
               WHERE enabled = 1 AND lower(trim(cron_expr)) LIKE '@at %'
               ORDER BY created_at ASC"""
        )
        for row in await cursor.fetchall():
            run_at = one_shot_cron_expr_to_run_at(row["cron_expr"] or "")
            if not run_at:
                continue
            out.append(
                {
                    "id": encode_one_shot_reminder_id(int(row["id"])),
                    "run_at": run_at,
                }
            )
        # Legacy fallback (pre-migration rows).
        cursor = await self._conn.execute(
            "SELECT id, run_at FROM reminders WHERE status = 'pending' ORDER BY run_at ASC",
            (),
        )
        rows = await cursor.fetchall()
        out.extend(dict(r) for r in rows)
        return out

    async def get_pending_reminder_by_id(self, reminder_id: int) -> dict[str, Any] | None:
        """Get a single pending reminder by ID for firing.

        Returns dict with keys: id, user_id, channel, channel_target, message
        Returns None if reminder doesn't exist or isn't pending.
        """
        if not self._conn:
            await self.connect()

        cursor = await self._conn.execute(
            """
            SELECT id, user_id, channel, channel_target, message
            FROM reminders
            WHERE id = ? AND status = 'pending'
            """,
            (reminder_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_reminder_sent(self, reminder_id: int) -> None:
        if not self._conn:
            await self.connect()
        one_shot_id = decode_one_shot_reminder_id(reminder_id)
        if one_shot_id is not None:
            cursor = await self._conn.execute(
                "SELECT user_id, channel, channel_target, message, cron_expr FROM cron_jobs WHERE id = ?",
                (one_shot_id,),
            )
            row = await cursor.fetchone()
            if row:
                run_at = one_shot_cron_expr_to_run_at(row["cron_expr"] or "") or datetime.now(
                    timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                await self._conn.execute(
                    """INSERT INTO reminders (user_id, channel, channel_target, message, run_at, status, created_at)
                       VALUES (?, ?, ?, ?, ?, 'sent', datetime('now'))""",
                    (
                        row["user_id"],
                        row["channel"],
                        row["channel_target"] or "",
                        row["message"] or "Reminder",
                        run_at,
                    ),
                )
                await self._conn.execute("DELETE FROM cron_jobs WHERE id = ?", (one_shot_id,))
        else:
            await self._conn.execute("UPDATE reminders SET status = 'sent' WHERE id = ?", (reminder_id,))
        await self._conn.commit()

    async def get_notifications(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        # Pending one-shot reminders are stored in cron_jobs.
        pending_rows: list[dict[str, Any]] = []
        cursor = await self._conn.execute(
            """SELECT id, message, cron_expr, channel, created_at
               FROM cron_jobs
               WHERE user_id = ? AND enabled = 1 AND lower(trim(cron_expr)) LIKE '@at %'
               ORDER BY created_at DESC""",
            (user_id,),
        )
        for row in await cursor.fetchall():
            run_at = one_shot_cron_expr_to_run_at(row["cron_expr"] or "")
            if not run_at:
                continue
            pending_rows.append(
                {
                    "id": encode_one_shot_reminder_id(int(row["id"])),
                    "message": row["message"] or "Reminder",
                    "run_at": run_at,
                    "status": "pending",
                    "channel": row["channel"] or "web",
                    "created_at": row["created_at"] or "",
                }
            )
        # Sent/legacy reminders history stays in reminders table.
        cursor = await self._conn.execute(
            """SELECT id, message, run_at, status, channel, created_at FROM reminders
               WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
            (user_id, max(limit * 2, limit)),
        )
        rows = await cursor.fetchall()
        items = pending_rows + [dict(r) for r in rows]
        items.sort(
            key=lambda r: (
                str(r.get("created_at") or ""),
                int(r.get("id") or 0),
            ),
            reverse=True,
        )
        return items[:limit]

    async def get_pending_reminders_for_user(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Pending reminders for context (id, message, run_at)."""
        if not self._conn:
            await self.connect()
        items = await self.get_notifications(user_id, limit=max(limit * 3, 50))
        pending = [r for r in items if (r.get("status") or "").lower() == "pending"]
        pending.sort(key=lambda r: str(r.get("run_at") or ""))
        return [
            {
                "id": int(r.get("id") or 0),
                "message": r.get("message") or "Reminder",
                "run_at": r.get("run_at") or "",
            }
            for r in pending[:limit]
        ]

    async def delete_reminder(self, reminder_id: int, user_id: str) -> bool:
        if not self._conn:
            await self.connect()
        one_shot_id = decode_one_shot_reminder_id(reminder_id)
        if one_shot_id is not None:
            cursor = await self._conn.execute(
                """DELETE FROM cron_jobs
                   WHERE id = ? AND user_id = ? AND lower(trim(cron_expr)) LIKE '@at %'""",
                (one_shot_id, user_id),
            )
            await self._conn.commit()
            return cursor.rowcount > 0

        # Backward compatibility: allow deleting one-shot by raw cron id too.
        cursor = await self._conn.execute(
            """DELETE FROM cron_jobs
               WHERE id = ? AND user_id = ? AND lower(trim(cron_expr)) LIKE '@at %'""",
            (reminder_id, user_id),
        )
        if cursor.rowcount > 0:
            await self._conn.commit()
            return True

        cursor = await self._conn.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def migrate_legacy_pending_reminders_to_one_shot(self) -> int:
        """Move old pending reminders rows into one-shot cron jobs."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """SELECT id, user_id, channel, channel_target, message, run_at, created_at
               FROM reminders
               WHERE status = 'pending'
               ORDER BY id ASC"""
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        moved = 0
        for row in rows:
            run_at = normalize_iso_utc(row.get("run_at") or "")
            if not run_at:
                continue
            name = f"{ONE_SHOT_REMINDER_NAME_PREFIX}legacy:{int(row['id'])}"
            cron_expr = run_at_to_one_shot_cron_expr(run_at)
            await self._conn.execute(
                """INSERT OR IGNORE INTO cron_jobs
                   (user_id, name, cron_expr, tz, message, channel, channel_target, enabled, created_at)
                   VALUES (?, ?, ?, '', ?, ?, ?, 1, ?)""",
                (
                    row["user_id"],
                    name,
                    cron_expr,
                    row.get("message") or "Reminder",
                    row.get("channel") or "web",
                    row.get("channel_target") or "",
                    row.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await self._conn.execute("DELETE FROM reminders WHERE id = ?", (row["id"],))
            moved += 1
        if moved:
            await self._conn.commit()
        return moved

    # Cron jobs (Claw-style recurring)
    async def add_cron_job(
        self,
        user_id: str,
        name: str,
        cron_expr: str,
        message: str,
        tz: str | None = None,
        channel: str = "web",
        channel_target: str = "",
        payload_kind: str = "agentturn",
        tlg_call: bool = False,
    ) -> int:
        """Insert or replace cron job by (user_id, name). Returns id."""
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO cron_jobs (user_id, name, cron_expr, tz, message, channel, channel_target, enabled, payload_kind, tlg_call, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, datetime('now'))
               ON CONFLICT(user_id, name) DO UPDATE SET cron_expr=excluded.cron_expr, tz=excluded.tz,
               message=excluded.message, channel=excluded.channel, channel_target=excluded.channel_target, enabled=1,
               payload_kind=excluded.payload_kind, tlg_call=excluded.tlg_call""",
            (user_id, name.strip(), cron_expr.strip(), tz or "", message.strip(), channel, channel_target or "", payload_kind, 1 if tlg_call else 0),
        )
        await self._conn.commit()
        cursor = await self._conn.execute("SELECT id FROM cron_jobs WHERE user_id = ? AND name = ?", (user_id, name.strip()))
        row = await cursor.fetchone()
        return row["id"] if row else 0

    async def get_cron_jobs(self, user_id: str) -> list[dict[str, Any]]:
        """List recurring cron jobs for user (one-shot reminders are excluded)."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """SELECT id, name, cron_expr, tz, message, channel, channel_target, enabled, payload_kind, tlg_call, created_at
               FROM cron_jobs
               WHERE user_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_all_enabled_cron_jobs(self) -> list[dict[str, Any]]:
        """All enabled cron jobs (for scheduler reload)."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT id, user_id, name, cron_expr, tz, message, channel, channel_target, payload_kind, tlg_call FROM cron_jobs WHERE enabled = 1"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_cron_job(self, job_id: int) -> dict[str, Any] | None:
        """Get one cron job by id."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute("SELECT * FROM cron_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_cron_job(
        self,
        job_id: int,
        cron_expr: str | None = None,
        tz: str | None = None,
        message: str | None = None,
        name: str | None = None,
        enabled: int | None = None,
        channel: str | None = None,
        channel_target: str | None = None,
        payload_kind: str | None = None,
        tlg_call: bool | None = None,
    ) -> bool:
        """Update an existing cron job by id. Only non-None fields are updated."""
        if not self._conn:
            await self.connect()
        updates = []
        params = []
        if name is not None:
            name_norm = name.strip()
            if not name_norm:
                return False
            updates.append("name = ?")
            params.append(name_norm)
        if cron_expr is not None:
            updates.append("cron_expr = ?")
            params.append(cron_expr.strip())
        if tz is not None:
            updates.append("tz = ?")
            params.append(tz.strip())
        if message is not None:
            updates.append("message = ?")
            params.append(message.strip())
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        if channel is not None:
            updates.append("channel = ?")
            params.append(channel.strip().lower())
        if channel_target is not None:
            updates.append("channel_target = ?")
            params.append(channel_target.strip())
        if payload_kind is not None:
            updates.append("payload_kind = ?")
            params.append(payload_kind.strip().lower())
        if tlg_call is not None:
            updates.append("tlg_call = ?")
            params.append(1 if tlg_call else 0)

        if not updates:
            return True
        params.append(job_id)
        try:
            cursor = await self._conn.execute(
                f"UPDATE cron_jobs SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            await self._conn.commit()
            return cursor.rowcount > 0
        except aiosqlite.IntegrityError:
            # Likely UNIQUE(user_id, name) conflict on rename.
            return False

    async def delete_cron_job(self, job_id: int) -> bool:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def delete_cron_job_by_name(self, user_id: str, name: str) -> bool:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute("DELETE FROM cron_jobs WHERE user_id = ? AND name = ?", (user_id, name.strip()))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def add_cron_job_run(
        self,
        *,
        cron_job_id: int,
        user_id: str,
        trigger: str,
        run_mode: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
    ) -> int:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """INSERT INTO cron_job_runs
               (cron_job_id, user_id, trigger, run_mode, status, output, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                int(cron_job_id),
                (user_id or "default").strip() or "default",
                (trigger or "schedule").strip() or "schedule",
                (run_mode or "due").strip() or "due",
                (status or "unknown").strip() or "unknown",
                (output or "").strip()[:4000] or None,
                (error or "").strip()[:2000] or None,
            ),
        )
        await self._conn.commit()
        return int(cursor.lastrowid or 0)

    async def get_cron_job_runs(
        self,
        *,
        user_id: str,
        cron_job_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        lim = max(1, min(int(limit or 20), 100))
        cursor = await self._conn.execute(
            """SELECT id, cron_job_id, user_id, trigger, run_mode, status, output, error, created_at
               FROM cron_job_runs
               WHERE user_id = ? AND cron_job_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            ((user_id or "default").strip() or "default", int(cron_job_id), lim),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_reminder(
        self,
        reminder_id: int,
        user_id: str,
        *,
        message: str | None = None,
        run_at: str | None = None,
    ) -> bool:
        """Update pending reminder fields by id.

        One-shot reminders are backed by cron_jobs (@at). Legacy pending reminders
        are kept for backward compatibility.
        """
        if not self._conn:
            await self.connect()

        one_shot_id = decode_one_shot_reminder_id(reminder_id)
        if one_shot_id is not None:
            updates = []
            params: list[Any] = []
            if message is not None:
                updates.append("message = ?")
                params.append(message.strip() or "Reminder")
            if run_at is not None:
                run_at_norm = normalize_iso_utc(run_at)
                if not run_at_norm:
                    return False
                updates.append("cron_expr = ?")
                params.append(run_at_to_one_shot_cron_expr(run_at_norm))
            if not updates:
                return True
            params.extend([one_shot_id, user_id])
            cursor = await self._conn.execute(
                f"""UPDATE cron_jobs
                    SET {', '.join(updates)}
                    WHERE id = ? AND user_id = ? AND lower(trim(cron_expr)) LIKE '@at %'""",
                tuple(params),
            )
            await self._conn.commit()
            return cursor.rowcount > 0

        # Backward compatibility: support direct legacy reminder rows.
        updates = []
        params = []
        if message is not None:
            updates.append("message = ?")
            params.append(message.strip() or "Reminder")
        if run_at is not None:
            run_at_norm = normalize_iso_utc(run_at)
            if not run_at_norm:
                return False
            updates.append("run_at = ?")
            params.append(run_at_norm)
        if not updates:
            return True
        params.extend([reminder_id, user_id])
        cursor = await self._conn.execute(
            f"""UPDATE reminders
                SET {', '.join(updates)}
                WHERE id = ? AND user_id = ? AND status = 'pending'""",
            tuple(params),
        )
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

    async def get_spotify_retry_request(self, user_id: str) -> dict[str, Any] | None:
        """Last play request that failed (e.g. no devices) so 'Done' / 'Try again' can retry."""
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT play_query, track_uri, created_at FROM spotify_retry_request WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_spotify_retry_request(self, user_id: str, play_query: str, track_uri: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """INSERT INTO spotify_retry_request (user_id, play_query, track_uri, created_at)
               VALUES (?, ?, ?, datetime('now')) ON CONFLICT(user_id) DO UPDATE SET
               play_query = ?, track_uri = ?, created_at = datetime('now')""",
            (user_id, play_query, track_uri, play_query, track_uri),
        )
        await self._conn.commit()

    async def clear_spotify_retry_request(self, user_id: str) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute("DELETE FROM spotify_retry_request WHERE user_id = ?", (user_id,))
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
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, pending_location_request, updated_at)
               VALUES (?, 'normal', '{DEFAULT_MAIN_PROVIDER}', datetime('now'), datetime('now'))
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
            f"""INSERT INTO user_settings (user_id, mood, default_ai_provider, fallback_providers, updated_at)
               VALUES (?, 'normal', '{DEFAULT_MAIN_PROVIDER}', ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET fallback_providers = ?, updated_at = datetime('now')""",
            (user_id, providers_csv, providers_csv),
        )
        await self._conn.commit()

    async def get_provider_runtime_states(
        self,
        user_id: str,
        providers: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get runtime states for providers (enabled/manual + auto-disabled)."""
        if not self._conn:
            await self.connect()

        requested = [str(p or "").strip().lower() for p in (providers or MAIN_PROVIDER_CHAIN) if str(p or "").strip()]
        deduped: list[str] = []
        seen: set[str] = set()
        for provider in requested:
            if provider in seen:
                continue
            seen.add(provider)
            deduped.append(provider)
        if not deduped:
            return {}

        placeholders = ",".join("?" for _ in deduped)
        cursor = await self._conn.execute(
            f"""
            SELECT provider, enabled, auto_disabled, disabled_reason, updated_at
            FROM provider_runtime_state
            WHERE user_id = ? AND provider IN ({placeholders})
            """,
            (user_id, *deduped),
        )
        rows = await cursor.fetchall()
        found = {str(row["provider"] or "").strip().lower(): row for row in rows}
        out: dict[str, dict[str, Any]] = {}
        for provider in deduped:
            row = found.get(provider)
            out[provider] = {
                "enabled": bool(row["enabled"]) if row else True,
                "auto_disabled": bool(row["auto_disabled"]) if row else False,
                "disabled_reason": str(row["disabled_reason"] or "").strip() if row else "",
                "updated_at": str(row["updated_at"] or "").strip() if row else "",
            }
        return out

    async def set_provider_runtime_enabled(
        self,
        user_id: str,
        provider: str,
        enabled: bool,
    ) -> None:
        if not self._conn:
            await self.connect()
        provider_key = str(provider or "").strip().lower()
        if not provider_key:
            return
        await self._conn.execute(
            """
            INSERT INTO provider_runtime_state (
                user_id, provider, enabled, auto_disabled, disabled_reason, updated_at
            ) VALUES (?, ?, ?, 0, '', datetime('now'))
            ON CONFLICT(user_id, provider) DO UPDATE SET
                enabled = ?,
                auto_disabled = CASE WHEN ? = 1 THEN 0 ELSE auto_disabled END,
                disabled_reason = CASE WHEN ? = 1 THEN '' ELSE disabled_reason END,
                updated_at = datetime('now')
            """,
            (
                user_id,
                provider_key,
                1 if enabled else 0,
                1 if enabled else 0,
                1 if enabled else 0,
                1 if enabled else 0,
            ),
        )
        await self._conn.commit()

    async def mark_provider_auto_disabled(
        self,
        user_id: str,
        provider: str,
        reason: str,
    ) -> None:
        if not self._conn:
            await self.connect()
        provider_key = str(provider or "").strip().lower()
        if not provider_key:
            return
        reason_text = str(reason or "").strip().lower() or "error"
        await self._conn.execute(
            """
            INSERT INTO provider_runtime_state (
                user_id, provider, enabled, auto_disabled, disabled_reason, updated_at
            ) VALUES (?, ?, 1, 1, ?, datetime('now'))
            ON CONFLICT(user_id, provider) DO UPDATE SET
                auto_disabled = 1,
                disabled_reason = ?,
                updated_at = datetime('now')
            """,
            (user_id, provider_key, reason_text, reason_text),
        )
        await self._conn.commit()

    async def clear_provider_auto_disabled(self, user_id: str, provider: str) -> None:
        if not self._conn:
            await self.connect()
        provider_key = str(provider or "").strip().lower()
        if not provider_key:
            return
        await self._conn.execute(
            """
            INSERT INTO provider_runtime_state (
                user_id, provider, enabled, auto_disabled, disabled_reason, updated_at
            ) VALUES (?, ?, 1, 0, '', datetime('now'))
            ON CONFLICT(user_id, provider) DO UPDATE SET
                auto_disabled = 0,
                disabled_reason = '',
                updated_at = datetime('now')
            """,
            (user_id, provider_key),
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

    async def add_exec_approval(
        self,
        *,
        approval_id: str,
        user_id: str,
        channel: str,
        channel_target: str,
        command: str,
        binary: str,
        timeout_sec: int | None = None,
        workdir: str | None = None,
        background: bool = False,
        pty: bool = False,
    ) -> None:
        if not self._conn:
            await self.connect()
        await self._conn.execute(
            """
            INSERT INTO exec_approvals (
                approval_id, user_id, channel, channel_target, command, binary,
                timeout_sec, workdir, background, pty, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
            """,
            (
                approval_id,
                user_id,
                channel,
                channel_target,
                command,
                binary,
                timeout_sec if isinstance(timeout_sec, int) else None,
                (workdir or "").strip() or None,
                1 if background else 0,
                1 if pty else 0,
            ),
        )
        await self._conn.commit()

    async def get_exec_approval(self, approval_id: str) -> dict[str, Any] | None:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            "SELECT * FROM exec_approvals WHERE approval_id = ?",
            ((approval_id or "").strip(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_pending_exec_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self._conn:
            await self.connect()
        cursor = await self._conn.execute(
            """
            SELECT approval_id, user_id, channel, channel_target, command, binary, timeout_sec, workdir,
                   background, pty, status, decision, created_at, resolved_at
            FROM exec_approvals
            WHERE status = 'pending'
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 100)),),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def resolve_exec_approval(
        self,
        approval_id: str,
        *,
        status: str,
        decision: str | None = None,
    ) -> bool:
        if not self._conn:
            await self.connect()
        status_norm = (status or "").strip().lower()
        if status_norm not in ("approved", "denied", "executed", "expired"):
            status_norm = "denied"
        decision_norm = (decision or "").strip().lower() or None
        cur = await self._conn.execute(
            """
            UPDATE exec_approvals
            SET status = ?, decision = ?, resolved_at = datetime('now')
            WHERE approval_id = ? AND status = 'pending'
            """,
            (status_norm, decision_norm, (approval_id or "").strip()),
        )
        await self._conn.commit()
        return cur.rowcount > 0

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
