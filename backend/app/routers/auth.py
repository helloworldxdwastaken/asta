"""Authentication routes: login, user management."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db import get_db
from app.auth_utils import create_jwt, get_current_user_id, get_current_user_role, require_admin
from app.auth_middleware import invalidate_multi_user_cache

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class CreateUserIn(BaseModel):
    username: str
    password: str
    role: str = "user"


class RegisterIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordIn(BaseModel):
    new_password: str


@router.post("/auth/login")
async def login(body: LoginIn):
    import bcrypt
    db = get_db()
    await db.connect()
    user = await db.get_user_by_username(body.username)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid username or password")
    token = create_jwt(user["id"], user["username"], user["role"])
    return {
        "access_token": token,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    }


@router.post("/auth/register")
async def register(body: RegisterIn):
    """Self-registration — creates a 'user' role account."""
    import bcrypt
    # Allow registration only when multi-user mode is active (users table has rows)
    db = get_db()
    await db.connect()
    if not await db.has_any_users():
        raise HTTPException(403, "Registration is not available")
    if len(body.username.strip()) < 2:
        raise HTTPException(400, "Username must be at least 2 characters")
    if len(body.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    existing = await db.get_user_by_username(body.username.strip())
    if existing:
        raise HTTPException(409, "Username already exists")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = await db.create_user(body.username.strip(), pw_hash, "user")
    invalidate_multi_user_cache()
    return {"user": {"id": user["id"], "username": user["username"], "role": user["role"]}}


@router.get("/auth/me")
async def get_me(request: Request):
    user_id = get_current_user_id(request)
    role = get_current_user_role(request)
    username = getattr(request.state, "username", "")
    return {"id": user_id, "username": username, "role": role}


@router.post("/auth/change-password")
async def change_password(request: Request, body: ChangePasswordIn):
    import bcrypt
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if not bcrypt.checkpw(body.current_password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Current password is incorrect")
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    await db.update_user_password(user_id, new_hash)
    return {"ok": True}


# ── Admin-only user management ────────────────────────────────────────────────


@router.get("/auth/users")
async def list_users(request: Request):
    require_admin(request)
    db = get_db()
    await db.connect()
    users = await db.list_users()
    return {"users": users}


@router.post("/auth/users")
async def create_user(request: Request, body: CreateUserIn):
    import bcrypt
    require_admin(request)
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "Role must be 'admin' or 'user'")
    if len(body.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    db = get_db()
    await db.connect()
    existing = await db.get_user_by_username(body.username)
    if existing:
        raise HTTPException(409, "Username already exists")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = await db.create_user(body.username, pw_hash, body.role)
    invalidate_multi_user_cache()
    return {"user": user}


@router.delete("/auth/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    require_admin(request)
    admin_id = get_current_user_id(request)
    if user_id == admin_id:
        raise HTTPException(400, "Cannot delete yourself")
    db = get_db()
    await db.connect()
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    await db.delete_user(user_id)
    invalidate_multi_user_cache()
    return {"ok": True}


@router.put("/auth/users/{user_id}/reset-password")
async def reset_password(request: Request, user_id: str, body: ResetPasswordIn):
    import bcrypt
    require_admin(request)
    if len(body.new_password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    db = get_db()
    await db.connect()
    user = await db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    await db.update_user_password(user_id, new_hash)
    return {"ok": True}
