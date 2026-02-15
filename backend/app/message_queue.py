"""Per-key async serialization for inbound channel messages.

OpenClaw queues by session key; this module provides a simple per-key lock so
channels can enforce in-order handling where needed.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging

_locks: dict[str, asyncio.Lock] = {}
_locks_meta_lock = asyncio.Lock()
MAX_MESSAGE_LOCKS = 500

logger = logging.getLogger(__name__)


def _cleanup_stale_message_locks() -> None:
    """Remove unlocked locks when dict grows too large."""
    if len(_locks) <= MAX_MESSAGE_LOCKS:
        return

    to_remove = []
    for key, lock in list(_locks.items()):
        if not lock.locked():
            to_remove.append(key)
        if len(to_remove) >= MAX_MESSAGE_LOCKS // 2:
            break

    for key in to_remove:
        _locks.pop(key, None)

    if to_remove:
        logger.debug("Cleaned up %d stale message locks", len(to_remove))


async def _get_lock(key: str) -> asyncio.Lock:
    """Thread-safe lock factory with cleanup."""
    async with _locks_meta_lock:
        _cleanup_stale_message_locks()  # Opportunistic cleanup

        if key not in _locks:
            _locks[key] = asyncio.Lock()
        return _locks[key]


@asynccontextmanager
async def queue_key(key: str):
    """Serialize work for a given key."""
    lock = await _get_lock(key)
    async with lock:
        yield
