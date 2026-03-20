"""Test that DB schema creation works on a fresh database."""

import asyncio
import tempfile
import os
import logging

import aiosqlite


async def _init_fresh_db(db_path: str):
    """Open a fresh DB and run init_schema."""
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    from app.db_schema import init_schema
    await init_schema(conn, logging.getLogger("test"))
    return conn


EXPECTED_TABLES = [
    "conversations",
    "messages",
    "tasks",
    "reminders",
    "user_settings",
    "api_keys",
    "skill_toggles",
    "provider_models",
    "provider_runtime_state",
    "user_location",
    "spotify_user_tokens",
    "pending_spotify_play",
    "spotify_retry_request",
    "saved_audio_notes",
    "pending_learn_about",
    "system_config",
    "exec_approvals",
    "allowed_paths",
    "cron_jobs",
    "cron_job_runs",
    "subagent_runs",
    "usage_stats",
    "conversation_folders",
    "users",
    "studio_channels",
    "studio_projects",
    "studio_assets",
    "studio_renders",
]


def test_fresh_db_creates_all_tables():
    """Create a temp DB, init schema, verify all expected tables exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        async def _run():
            conn = await _init_fresh_db(db_path)
            try:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                rows = await cursor.fetchall()
                table_names = {row[0] for row in rows}
                return table_names
            finally:
                await conn.close()

        table_names = asyncio.run(_run())

        for expected in EXPECTED_TABLES:
            assert expected in table_names, f"Missing table: {expected}"


def test_fresh_db_idempotent():
    """Running init_schema twice should not error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        async def _run():
            conn = await _init_fresh_db(db_path)
            # Run again -- should be idempotent
            from app.db_schema import init_schema
            await init_schema(conn, logging.getLogger("test"))
            await conn.close()

        asyncio.run(_run())


def test_conversations_has_folder_id_column():
    """After init, conversations table should have the folder_id migration column."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        async def _run():
            conn = await _init_fresh_db(db_path)
            try:
                cursor = await conn.execute("PRAGMA table_info(conversations)")
                cols = [row[1] for row in await cursor.fetchall()]
                return cols
            finally:
                await conn.close()

        cols = asyncio.run(_run())
        assert "folder_id" in cols
        assert "title" in cols
