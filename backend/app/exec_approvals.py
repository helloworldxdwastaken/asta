"""Pending exec approval helpers (OpenClaw-style lite)."""
from __future__ import annotations

import shlex
from pathlib import Path
from uuid import uuid4

from app.db import Db

APPROVAL_ID_PREFIX = "app_"


def normalize_exec_binary(raw: str) -> str:
    token = (raw or "").strip().lower()
    if not token:
        return ""
    token = token.rstrip(",")
    token = token.rsplit("/", 1)[-1]
    return token


def extract_exec_binary(command: str) -> str:
    cmd = (command or "").strip()
    if not cmd:
        return ""
    try:
        parts = shlex.split(cmd)
    except Exception:
        return ""
    if not parts:
        return ""
    return normalize_exec_binary(Path(parts[0]).name)


def new_approval_id() -> str:
    return f"{APPROVAL_ID_PREFIX}{uuid4().hex[:8]}"


async def create_pending_exec_approval(
    *,
    db: Db,
    user_id: str,
    channel: str,
    channel_target: str,
    command: str,
    timeout_sec: int | None = None,
    workdir: str | None = None,
    background: bool = False,
    pty: bool = False,
) -> tuple[str, str]:
    binary = extract_exec_binary(command)
    approval_id = new_approval_id()
    await db.add_exec_approval(
        approval_id=approval_id,
        user_id=user_id,
        channel=(channel or "").strip().lower() or "web",
        channel_target=(channel_target or "").strip(),
        command=(command or "").strip(),
        binary=binary,
        timeout_sec=timeout_sec,
        workdir=workdir,
        background=background,
        pty=pty,
    )
    return approval_id, binary
