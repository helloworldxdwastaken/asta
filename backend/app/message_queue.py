"""Per-key async serialization for inbound channel messages.

OpenClaw queues by session key; this module provides a simple per-key lock so
channels can enforce in-order handling where needed.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@asynccontextmanager
async def queue_key(key: str):
    """Serialize work for a given key."""
    lock = _locks[key]
    async with lock:
        yield
