"""Cron jobs API (Claw-style): add, list, remove recurring jobs."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_db
from app.cron_runner import add_cron_job_to_scheduler, reload_cron_jobs
from app.tasks.scheduler import get_scheduler

router = APIRouter()


class CronAddIn(BaseModel):
    name: str
    cron_expr: str  # 5-field e.g. "0 8 * * *"
    message: str
    tz: str | None = None
    channel: str = "web"
    channel_target: str = ""


class CronUpdateIn(BaseModel):
    cron_expr: str | None = None
    tz: str | None = None
    message: str | None = None


@router.get("/cron")
@router.get("/api/cron")
async def list_cron(user_id: str = "default"):
    """List cron jobs for the user."""
    db = get_db()
    await db.connect()
    jobs = await db.get_cron_jobs(user_id)
    return {"cron_jobs": jobs}


@router.post("/cron")
@router.post("/api/cron")
async def add_cron(body: CronAddIn, user_id: str = "default"):
    """Add or update a cron job (Claw-style)."""
    name = (body.name or "").strip()
    cron_expr = (body.cron_expr or "").strip()
    message = (body.message or "").strip()
    if not name or not cron_expr or not message:
        raise HTTPException(400, "name, cron_expr, and message are required")
    db = get_db()
    await db.connect()
    job_id = await db.add_cron_job(
        user_id,
        name,
        cron_expr,
        message,
        tz=body.tz,
        channel=body.channel or "web",
        channel_target=body.channel_target or "",
    )
    sch = get_scheduler()
    add_cron_job_to_scheduler(sch, job_id, cron_expr, body.tz)
    return {"id": job_id, "name": name, "cron_expr": cron_expr}


@router.put("/cron/{job_id:int}")
@router.put("/api/cron/{job_id:int}")
async def update_cron(job_id: int, body: CronUpdateIn):
    """Update a cron job (schedule, timezone, message) and reschedule it."""
    from app.cron_runner import CRON_JOB_PREFIX
    db = get_db()
    await db.connect()
    job = await db.get_cron_job(job_id)
    if not job:
        raise HTTPException(404, "Cron job not found")
    cron_expr = (body.cron_expr or "").strip() or None
    tz = (body.tz or "").strip() if body.tz is not None else None
    message = (body.message or "").strip() if body.message is not None else None
    await db.update_cron_job(job_id, cron_expr=cron_expr, tz=tz, message=message)
    # Reschedule: remove old, add new with updated expr/tz
    sch = get_scheduler()
    sid = f"{CRON_JOB_PREFIX}{job_id}"
    if sch.get_job(sid):
        sch.remove_job(sid)
    updated = await db.get_cron_job(job_id)
    expr = (updated.get("cron_expr") or "").strip()
    tz_str = (updated.get("tz") or "").strip() or None
    if expr:
        add_cron_job_to_scheduler(sch, job_id, expr, tz_str)
    return {"ok": True, "id": job_id, "cron_expr": expr, "tz": tz_str}


@router.delete("/cron/{job_id:int}")
@router.delete("/api/cron/{job_id:int}")
async def remove_cron(job_id: int):
    """Remove a cron job and unschedule it."""
    from app.cron_runner import CRON_JOB_PREFIX
    db = get_db()
    await db.connect()
    ok = await db.delete_cron_job(job_id)
    if not ok:
        raise HTTPException(404, "Cron job not found")
    sch = get_scheduler()
    sid = f"{CRON_JOB_PREFIX}{job_id}"
    if sch.get_job(sid):
        sch.remove_job(sid)
    return {"ok": True, "id": job_id}
