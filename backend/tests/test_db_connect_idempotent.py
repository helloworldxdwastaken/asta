import asyncio

import pytest

from app.db import get_db


@pytest.mark.asyncio
async def test_db_connect_is_idempotent_and_concurrency_safe():
    db = get_db()
    await db.connect()
    first_conn = db._conn
    assert first_conn is not None

    await db.connect()
    assert db._conn is first_conn

    await asyncio.gather(*(db.connect() for _ in range(8)))
    assert db._conn is first_conn
