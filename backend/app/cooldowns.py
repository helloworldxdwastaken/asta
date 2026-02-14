"""Simple per-user cooldown checks backed by system_config."""
from __future__ import annotations

import time


def _cooldown_key(user_id: str, action: str) -> str:
    safe_user = (user_id or "default").strip() or "default"
    safe_action = (action or "").strip().lower().replace(" ", "_")
    return f"cooldown:{safe_action}:{safe_user}"


async def is_cooldown_ready(db, user_id: str, action: str, cooldown_seconds: int) -> bool:
    """True when action can run now for this user."""
    if cooldown_seconds <= 0:
        return True
    raw = await db.get_system_config(_cooldown_key(user_id, action))
    if not raw:
        return True
    try:
        last_ts = int(float(raw))
    except Exception:
        return True
    return (int(time.time()) - last_ts) >= cooldown_seconds


async def mark_cooldown_now(db, user_id: str, action: str) -> None:
    """Record action use time for cooldown checks."""
    await db.set_system_config(_cooldown_key(user_id, action), str(int(time.time())))

