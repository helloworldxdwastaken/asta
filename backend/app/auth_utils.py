"""JWT creation/validation and request helpers for multi-user auth."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
from fastapi import Request, HTTPException

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_DAYS = 30

_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret:
        return _jwt_secret

    _jwt_secret = os.environ.get("ASTA_JWT_SECRET", "").strip()
    if _jwt_secret:
        return _jwt_secret

    # Auto-generate and persist
    _jwt_secret = secrets.token_hex(32)
    env_file = Path(__file__).resolve().parent.parent / ".env"
    from app.config import set_env_value
    set_env_value("ASTA_JWT_SECRET", _jwt_secret)
    return _jwt_secret


def create_jwt(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """Decode and validate a JWT. Returns payload dict or None if invalid/expired."""
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user_id(request: Request) -> str:
    """Extract user_id from request state (set by auth middleware)."""
    return getattr(request.state, "user_id", "default")


def get_current_user_role(request: Request) -> str:
    """Extract user role from request state (set by auth middleware)."""
    return getattr(request.state, "user_role", "user")


def require_admin(request: Request) -> None:
    """Raise 403 if current user is not admin."""
    if get_current_user_role(request) != "admin":
        raise HTTPException(403, "Admin access required")
