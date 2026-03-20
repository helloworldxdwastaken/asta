"""Studio API: video production hub — channels, projects, assets, renders."""
from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.db import get_db
from app.auth_utils import get_current_user_id, require_admin

router = APIRouter()

STUDIO_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace", "studio", "assets"
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class ChannelCreateIn(BaseModel):
    channel_name: str
    channel_youtube_id: str | None = None
    avatar_url: str | None = None
    default_voice: str = "male"
    default_caption_preset: str = "standard"


class ChannelUpdateIn(BaseModel):
    channel_name: str | None = None
    channel_youtube_id: str | None = None
    avatar_url: str | None = None
    default_voice: str | None = None
    default_caption_preset: str | None = None
    enabled: bool | None = None


class ProjectCreateIn(BaseModel):
    title: str
    topic: str | None = None
    channel_id: str | None = None
    format: str = "standard"  # short, standard, long


class ProjectUpdateIn(BaseModel):
    title: str | None = None
    topic: str | None = None
    channel_id: str | None = None
    format: str | None = None
    status: str | None = None
    script_md: str | None = None
    metadata_json: str | None = None
    voice: str | None = None
    scheduled_at: str | None = None
    render_progress: int | None = None
    render_error: str | None = None
    video_path: str | None = None
    upload_result_json: str | None = None
    work_dir: str | None = None


class AssetUpdateIn(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    enabled: bool | None = None
    channel_id: str | None = None


# ── Channels ──────────────────────────────────────────────────────────────────

@router.get("/api/studio/channels")
async def list_channels(request: Request):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    channels = await db.get_studio_channels(user_id)
    return {"channels": channels}


@router.post("/api/studio/channels")
async def create_channel(request: Request, body: ChannelCreateIn):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    channel_id = str(uuid4())
    await db.add_studio_channel(
        user_id=user_id, channel_id=channel_id,
        channel_name=body.channel_name,
        channel_youtube_id=body.channel_youtube_id,
        avatar_url=body.avatar_url,
        default_voice=body.default_voice,
        default_caption_preset=body.default_caption_preset,
    )
    channel = await db.get_studio_channel(channel_id)
    return {"channel": channel}


@router.put("/api/studio/channels/{channel_id}")
async def update_channel(request: Request, channel_id: str, body: ChannelUpdateIn):
    require_admin(request)
    db = get_db()
    existing = await db.get_studio_channel(channel_id)
    if not existing:
        raise HTTPException(404, "Channel not found")
    kwargs = body.model_dump(exclude_none=True)
    if "enabled" in kwargs:
        kwargs["enabled"] = 1 if kwargs["enabled"] else 0
    await db.update_studio_channel(channel_id, **kwargs)
    channel = await db.get_studio_channel(channel_id)
    return {"channel": channel}


@router.delete("/api/studio/channels/{channel_id}")
async def delete_channel(request: Request, channel_id: str):
    require_admin(request)
    db = get_db()
    ok = await db.delete_studio_channel(channel_id)
    if not ok:
        raise HTTPException(404, "Channel not found")
    return {"ok": True}


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("/api/studio/projects")
async def list_projects(request: Request, channel_id: str | None = None, status: str | None = None):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    projects = await db.get_studio_projects(user_id, channel_id=channel_id, status=status)
    return {"projects": projects}


@router.post("/api/studio/projects")
async def create_project(request: Request, body: ProjectCreateIn):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    project_id = str(uuid4())
    await db.add_studio_project(
        user_id=user_id, project_id=project_id,
        title=body.title, topic=body.topic,
        channel_id=body.channel_id, format=body.format,
    )
    project = await db.get_studio_project(project_id)
    return {"project": project}


@router.get("/api/studio/projects/{project_id}")
async def get_project(request: Request, project_id: str):
    require_admin(request)
    db = get_db()
    project = await db.get_studio_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {"project": project}


@router.put("/api/studio/projects/{project_id}")
async def update_project(request: Request, project_id: str, body: ProjectUpdateIn):
    require_admin(request)
    db = get_db()
    existing = await db.get_studio_project(project_id)
    if not existing:
        raise HTTPException(404, "Project not found")
    kwargs = body.model_dump(exclude_none=True)
    await db.update_studio_project(project_id, **kwargs)
    project = await db.get_studio_project(project_id)
    return {"project": project}


@router.delete("/api/studio/projects/{project_id}")
async def delete_project(request: Request, project_id: str):
    require_admin(request)
    db = get_db()
    ok = await db.delete_studio_project(project_id)
    if not ok:
        raise HTTPException(404, "Project not found")
    return {"ok": True}


# ── Assets ────────────────────────────────────────────────────────────────────

@router.get("/api/studio/assets")
async def list_assets(request: Request, asset_type: str | None = None, channel_id: str | None = None):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    assets = await db.get_studio_assets(user_id, asset_type=asset_type, channel_id=channel_id)
    return {"assets": assets}


@router.post("/api/studio/assets")
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    asset_type: str = Form(...),
    channel_id: str = Form(""),
):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()

    valid_types = {"intro", "outro", "subscribe", "watermark", "music", "overlay"}
    if asset_type not in valid_types:
        raise HTTPException(400, f"asset_type must be one of: {', '.join(sorted(valid_types))}")

    # Save file
    asset_id = str(uuid4())
    user_dir = os.path.join(STUDIO_ASSETS_DIR, user_id, asset_type)
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1] or ".mp4"
    file_path = os.path.join(user_dir, f"{asset_id}{ext}")
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    await db.add_studio_asset(
        user_id=user_id, asset_id=asset_id, name=name,
        asset_type=asset_type, file_path=file_path,
        channel_id=channel_id or None,
    )
    asset = await db.get_studio_assets(user_id)
    # Return just the new one
    new_asset = next((a for a in asset if a["id"] == asset_id), None)
    return {"asset": new_asset}


@router.put("/api/studio/assets/{asset_id}")
async def update_asset(request: Request, asset_id: str, body: AssetUpdateIn):
    require_admin(request)
    db = get_db()
    kwargs = body.model_dump(exclude_none=True)
    if "enabled" in kwargs:
        kwargs["enabled"] = 1 if kwargs["enabled"] else 0
    ok = await db.update_studio_asset(asset_id, **kwargs)
    if not ok:
        raise HTTPException(404, "Asset not found")
    assets = await db.get_studio_assets(get_current_user_id(request))
    asset = next((a for a in assets if a["id"] == asset_id), None)
    return {"asset": asset} if asset else {"ok": True}


@router.delete("/api/studio/assets/{asset_id}")
async def delete_asset(request: Request, asset_id: str):
    require_admin(request)
    db = get_db()
    ok = await db.delete_studio_asset(asset_id)
    if not ok:
        raise HTTPException(404, "Asset not found")
    return {"ok": True}


# ── Renders ───────────────────────────────────────────────────────────────────

@router.get("/api/studio/renders")
async def list_renders(request: Request, project_id: str | None = None):
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    renders = await db.get_studio_renders(user_id, project_id=project_id)
    return {"renders": renders}


@router.get("/api/studio/renders/{render_id}")
async def get_render(request: Request, render_id: str):
    require_admin(request)
    db = get_db()
    render = await db.get_studio_render(render_id)
    if not render:
        raise HTTPException(404, "Render not found")
    return {"render": render}
