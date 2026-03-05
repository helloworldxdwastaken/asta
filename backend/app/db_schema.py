"""Database schema creation and migrations for Asta.

Separated from db.py to keep the Db class focused on data-access methods.
Call ``await init_schema(conn, logger)`` from ``Db.connect()`` after opening
the aiosqlite connection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.provider_flow import DEFAULT_MAIN_PROVIDER

if TYPE_CHECKING:
    import aiosqlite


async def init_schema(conn: "aiosqlite.Connection", logger: logging.Logger) -> None:
    """Create all tables/indexes (IF NOT EXISTS) then run column migrations."""
    await conn.executescript(f"""
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
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'default',
            provider TEXT NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_usage_provider_created ON usage_stats(provider, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_usage_user_created ON usage_stats(user_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS conversation_folders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'web',
            name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#6366F1',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_folders_user_channel ON conversation_folders(user_id, channel);

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );
    """)
    await conn.commit()

    # --- Migration: create admin from existing "default" data ---
    await _migrate_default_to_admin(conn, logger)

    # --- Migrations: add columns to existing installs ---

    # conversations: folder_id, title
    cursor_conv = await conn.execute("PRAGMA table_info(conversations)")
    conv_cols = [row["name"] for row in await cursor_conv.fetchall()]
    if "folder_id" not in conv_cols:
        try:
            await conn.execute("ALTER TABLE conversations ADD COLUMN folder_id TEXT")
            await conn.commit()
        except Exception as e:
            logger.exception("Failed to add folder_id column to conversations: %s", e)
    if "title" not in conv_cols:
        try:
            await conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
            await conn.commit()
        except Exception as e:
            logger.exception("Failed to add title column to conversations: %s", e)

    # cron_jobs: payload_kind, tlg_call
    cursor = await conn.execute("PRAGMA table_info(cron_jobs)")
    cron_cols = [row["name"] for row in await cursor.fetchall()]
    if "payload_kind" not in cron_cols:
        try:
            await conn.execute(
                "ALTER TABLE cron_jobs ADD COLUMN payload_kind TEXT NOT NULL DEFAULT 'agentturn'"
            )
            await conn.commit()
        except Exception as e:
            logger.exception("Failed to add payload_kind column to cron_jobs: %s", e)
    if "tlg_call" not in cron_cols:
        try:
            await conn.execute(
                "ALTER TABLE cron_jobs ADD COLUMN tlg_call INTEGER NOT NULL DEFAULT 0"
            )
            await conn.commit()
        except Exception as e:
            logger.exception("Failed to add tlg_call column to cron_jobs: %s", e)

    # user_settings: several columns added over time
    cursor = await conn.execute("PRAGMA table_info(user_settings)")
    columns = [row["name"] for row in await cursor.fetchall()]
    _user_settings_migrations = [
        (
            "default_ai_provider",
            f"ALTER TABLE user_settings ADD COLUMN default_ai_provider TEXT NOT NULL DEFAULT '{DEFAULT_MAIN_PROVIDER}'",
        ),
        (
            "pending_location_request",
            "ALTER TABLE user_settings ADD COLUMN pending_location_request TEXT",
        ),
        (
            "fallback_providers",
            "ALTER TABLE user_settings ADD COLUMN fallback_providers TEXT DEFAULT ''",
        ),
        (
            "thinking_level",
            "ALTER TABLE user_settings ADD COLUMN thinking_level TEXT NOT NULL DEFAULT 'off'",
        ),
        (
            "reasoning_mode",
            "ALTER TABLE user_settings ADD COLUMN reasoning_mode TEXT NOT NULL DEFAULT 'off'",
        ),
        (
            "final_mode",
            "ALTER TABLE user_settings ADD COLUMN final_mode TEXT NOT NULL DEFAULT 'off'",
        ),
    ]
    for col, sql in _user_settings_migrations:
        if col not in columns:
            try:
                await conn.execute(sql)
                await conn.commit()
            except Exception as e:
                logger.exception("Failed to add user_settings.%s column: %s", col, e)

    # subagent_runs: several columns added over time
    try:
        cursor = await conn.execute("PRAGMA table_info(subagent_runs)")
        sub_cols = [row["name"] for row in await cursor.fetchall()]
        _subagent_migrations = [
            ("model_override", "ALTER TABLE subagent_runs ADD COLUMN model_override TEXT"),
            ("thinking_override", "ALTER TABLE subagent_runs ADD COLUMN thinking_override TEXT"),
            (
                "run_timeout_seconds",
                "ALTER TABLE subagent_runs ADD COLUMN run_timeout_seconds INTEGER NOT NULL DEFAULT 0",
            ),
            ("archived_at", "ALTER TABLE subagent_runs ADD COLUMN archived_at TEXT"),
        ]
        for col, sql in _subagent_migrations:
            if col in sub_cols:
                continue
            try:
                await conn.execute(sql)
                await conn.commit()
            except Exception as e:
                logger.exception("Failed to add subagent_runs.%s column: %s", col, e)
    except Exception as e:
        logger.debug("subagent_runs table migration check skipped: %s", e)


async def _migrate_default_to_admin(conn: "aiosqlite.Connection", logger: logging.Logger) -> None:
    """One-time migration: if users table is empty and 'default' data exists, create admin and remap."""
    import os
    from uuid import uuid4
    from datetime import datetime, timezone

    cursor = await conn.execute("SELECT COUNT(*) FROM users")
    count = (await cursor.fetchone())[0]
    if count > 0:
        return  # Already have users, skip

    # Check if there's any existing data with user_id='default'
    cursor = await conn.execute("SELECT COUNT(*) FROM conversations WHERE user_id = 'default'")
    has_data = (await cursor.fetchone())[0] > 0

    if not has_data:
        # Fresh install — no migration needed, admin will be created on first login attempt
        return

    # Create admin user
    username = os.environ.get("ASTA_ADMIN_USERNAME", "admin")
    password = os.environ.get("ASTA_ADMIN_PASSWORD", "")
    if not password:
        import secrets
        password = secrets.token_urlsafe(16)
        logger.warning("=" * 60)
        logger.warning("AUTO-GENERATED ADMIN PASSWORD: %s", password)
        logger.warning("Username: %s", username)
        logger.warning("Save this password — it won't be shown again!")
        logger.warning("=" * 60)

    try:
        import bcrypt
    except ImportError:
        logger.error("bcrypt not installed — cannot create admin user. Run: pip install bcrypt")
        return

    admin_id = str(uuid4())
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)",
        (admin_id, username, pw_hash, now),
    )

    # Remap all tables with user_id='default' to admin UUID
    _tables_with_user_id = [
        "conversations", "tasks", "reminders", "user_settings", "skill_toggles",
        "provider_models", "provider_runtime_state", "user_location",
        "spotify_user_tokens", "pending_spotify_play", "spotify_retry_request",
        "saved_audio_notes", "pending_learn_about", "exec_approvals",
        "allowed_paths", "cron_jobs", "cron_job_runs", "subagent_runs",
        "usage_stats", "conversation_folders",
    ]
    for table in _tables_with_user_id:
        try:
            await conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id = 'default'", (admin_id,))
        except Exception as e:
            logger.debug("Migration skip %s: %s", table, e)

    # Update conversation IDs: default:web:xxx → admin_id:web:xxx
    cursor = await conn.execute("SELECT id FROM conversations WHERE id LIKE 'default:%'")
    rows = await cursor.fetchall()
    for row in rows:
        old_id = row[0]
        new_id = admin_id + old_id[7:]  # len("default") = 7
        await conn.execute("UPDATE conversations SET id = ? WHERE id = ?", (new_id, old_id))
        await conn.execute("UPDATE messages SET conversation_id = ? WHERE conversation_id = ?", (new_id, old_id))
        # Update folder references
        try:
            await conn.execute("UPDATE conversation_folders SET id = ? WHERE id = ?", (new_id, old_id))
        except Exception:
            pass

    await conn.commit()
    logger.info("✓ Migrated existing data from 'default' to admin user '%s' (id=%s)", username, admin_id)
