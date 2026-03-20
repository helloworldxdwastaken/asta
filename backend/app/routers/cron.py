"""Cron jobs API (Claw-style): add, list, remove recurring jobs."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db import get_db
from app.cron_runner import add_cron_job_to_scheduler, reload_cron_jobs
from app.tasks.scheduler import get_scheduler
from app.auth_utils import get_current_user_id, require_admin

router = APIRouter()


class CronAddIn(BaseModel):
    name: str
    cron_expr: str  # 5-field e.g. "0 8 * * *"
    message: str
    tz: str | None = None
    channel: str = "web"
    channel_target: str = ""
    payload_kind: str = "agentturn"
    tlg_call: bool = False


class CronUpdateIn(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    tz: str | None = None
    message: str | None = None
    enabled: bool | None = None
    payload_kind: str | None = None
    tlg_call: bool | None = None
    channel: str | None = None
    channel_target: str | None = None


@router.get("/cron/dashboard")
@router.get("/api/cron/dashboard")
async def cron_dashboard(request: Request):
    """Dashboard view: cron jobs enriched with last run, next run, linked agent."""
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    jobs = await db.get_cron_jobs(user_id)
    sch = get_scheduler()
    from app.cron_runner import CRON_JOB_PREFIX

    enriched = []
    for job in jobs:
        jid = job["id"]
        # Next run from scheduler
        sched_job = sch.get_job(f"{CRON_JOB_PREFIX}{jid}")
        next_run = None
        if sched_job and getattr(sched_job, "next_run_time", None):
            next_run = sched_job.next_run_time.isoformat()
        # Last run from DB
        runs = await db.get_cron_job_runs(user_id=user_id, cron_job_id=jid, limit=1)
        last_run = runs[0] if runs else None
        # Detect linked agent from message (e.g. "@YouTube Creator ...")
        agent_id = None
        msg = job.get("message", "")
        if msg.startswith("@"):
            agent_id = msg.split(" ", 1)[0][1:].lower().replace(" ", "-")
        enriched.append({
            **job,
            "next_run": next_run,
            "last_run": last_run,
            "agent_id": agent_id,
        })
    return {"cron_jobs": enriched}


@router.get("/cron/{job_id:int}/runs")
@router.get("/api/cron/{job_id:int}/runs")
async def list_cron_runs(request: Request, job_id: int, limit: int = 10):
    """Get recent runs for a cron job."""
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    runs = await db.get_cron_job_runs(user_id=user_id, cron_job_id=job_id, limit=limit)
    return {"runs": runs}


class YouTubeScheduleIn(BaseModel):
    niche: str = "tech"
    shorts_days: list[str] = ["1", "3", "5", "6"]   # Mon,Wed,Fri,Sat
    standard_days: list[str] = ["2", "4"]             # Tue,Thu
    hour: int = 9
    minute: int = 0
    tz: str | None = None


@router.post("/cron/youtube-schedule")
@router.post("/api/cron/youtube-schedule")
async def create_youtube_schedule(request: Request, body: YouTubeScheduleIn):
    """Create a full YouTube posting schedule (Shorts + Standard videos)."""
    require_admin(request)
    user_id = get_current_user_id(request)
    from app.db import validate_cron_expression

    db = get_db()
    await db.connect()
    sch = get_scheduler()
    created = []

    # Delete existing youtube schedule jobs first
    existing = await db.get_cron_jobs(user_id)
    for job in existing:
        if job.get("name", "").startswith("yt_"):
            await db.delete_cron_job(job["id"])
            from app.cron_runner import CRON_JOB_PREFIX
            sid = f"{CRON_JOB_PREFIX}{job['id']}"
            if sch.get_job(sid):
                sch.remove_job(sid)

    day_names = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat"}

    # Create Shorts jobs
    if body.shorts_days:
        dow = ",".join(body.shorts_days)
        cron_expr = f"{body.minute} {body.hour} * * {dow}"
        is_valid, err = validate_cron_expression(cron_expr, body.tz)
        if not is_valid:
            raise HTTPException(400, f"Invalid cron: {err}")
        days_label = "/".join(day_names.get(d, d) for d in body.shorts_days)
        prompt = (
            f"@YouTube Creator Create a YouTube Short about '{body.niche}'. "
            f"Find a trending subtopic, source footage, write a 45-second script, "
            f"and edit in short format (vertical 9:16, fast cuts). "
            f"Save for my review — do NOT upload."
        )
        job_id = await db.add_cron_job(
            user_id, f"yt_shorts_{days_label}", cron_expr, prompt,
            tz=body.tz, channel="web", payload_kind="agentturn",
        )
        add_cron_job_to_scheduler(sch, job_id, cron_expr, body.tz)
        created.append({"id": job_id, "name": f"yt_shorts_{days_label}", "type": "short", "cron_expr": cron_expr})

    # Create Standard video jobs
    if body.standard_days:
        dow = ",".join(body.standard_days)
        cron_expr = f"{body.minute} {body.hour} * * {dow}"
        is_valid, err = validate_cron_expression(cron_expr, body.tz)
        if not is_valid:
            raise HTTPException(400, f"Invalid cron: {err}")
        days_label = "/".join(day_names.get(d, d) for d in body.standard_days)
        prompt = (
            f"@YouTube Creator Create a standard YouTube video about '{body.niche}'. "
            f"Find a trending subtopic, source footage + photos, write a 3-minute script, "
            f"and edit in standard format (16:9, cinematic grade, captions). "
            f"Save for my review — do NOT upload."
        )
        job_id = await db.add_cron_job(
            user_id, f"yt_standard_{days_label}", cron_expr, prompt,
            tz=body.tz, channel="web", payload_kind="agentturn",
        )
        add_cron_job_to_scheduler(sch, job_id, cron_expr, body.tz)
        created.append({"id": job_id, "name": f"yt_standard_{days_label}", "type": "standard", "cron_expr": cron_expr})

    return {"ok": True, "created": created, "total": len(created)}


@router.get("/cron")
@router.get("/api/cron")
async def list_cron(request: Request):
    """List cron jobs for the user."""
    require_admin(request)
    user_id = get_current_user_id(request)
    db = get_db()
    await db.connect()
    jobs = await db.get_cron_jobs(user_id)
    return {"cron_jobs": jobs}


@router.post("/cron")
@router.post("/api/cron")
async def add_cron(request: Request, body: CronAddIn):
    """Add or update a cron job (Claw-style)."""
    require_admin(request)
    user_id = get_current_user_id(request)
    name = (body.name or "").strip()
    cron_expr = (body.cron_expr or "").strip()
    message = (body.message or "").strip()
    if not name or not cron_expr or not message:
        raise HTTPException(400, "name, cron_expr, and message are required")
    from app.db import validate_cron_expression

    is_valid, error_msg = validate_cron_expression(cron_expr, body.tz)
    if not is_valid:
        raise HTTPException(400, f"Invalid cron expression: {error_msg}")
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
        payload_kind=body.payload_kind,
        tlg_call=body.tlg_call,
    )
    sch = get_scheduler()
    add_cron_job_to_scheduler(sch, job_id, cron_expr, body.tz)
    return {"id": job_id, "name": name, "cron_expr": cron_expr}


@router.put("/cron/{job_id:int}")
@router.put("/api/cron/{job_id:int}")
async def update_cron(request: Request, job_id: int, body: CronUpdateIn):
    """Update a cron job (schedule, timezone, message) and reschedule it."""
    require_admin(request)
    user_id = get_current_user_id(request)
    from app.cron_runner import CRON_JOB_PREFIX
    db = get_db()
    await db.connect()
    job = await db.get_cron_job(job_id)
    if not job:
        raise HTTPException(404, "Cron job not found")
    # Verify ownership
    if job.get("user_id") != user_id:
        raise HTTPException(403, "Cron job does not belong to this user")
    name = (body.name or "").strip() if body.name is not None else None
    cron_expr = (body.cron_expr or "").strip() or None
    tz = (body.tz or "").strip() if body.tz is not None else None
    message = (body.message or "").strip() if body.message is not None else None

    if cron_expr is not None:
        from app.db import validate_cron_expression

        is_valid, error_msg = validate_cron_expression(cron_expr, tz)
        if not is_valid:
            raise HTTPException(400, f"Invalid cron expression: {error_msg}")

    ok = await db.update_cron_job(
        job_id,
        name=name,
        cron_expr=cron_expr,
        tz=tz,
        message=message,
        enabled=body.enabled,
        payload_kind=body.payload_kind,
        tlg_call=body.tlg_call,
        channel=body.channel,
        channel_target=body.channel_target,
    )
    if not ok:
        raise HTTPException(409, "Could not update cron job (duplicate name or job not found)")
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
    return {"ok": True, "id": job_id, "name": updated.get("name"), "cron_expr": expr, "tz": tz_str}


@router.post("/cron/{job_id:int}/run")
@router.post("/api/cron/{job_id:int}/run")
async def run_cron_now(request: Request, job_id: int):
    """Trigger a cron job immediately (manual run)."""
    require_admin(request)
    db = get_db()
    await db.connect()
    job = await db.get_cron_job(job_id)
    if not job:
        raise HTTPException(404, "Cron job not found")
    from app.cron_runner import run_cron_job_now
    result = await run_cron_job_now(job_id, run_mode="force")
    return {"ok": True, "id": job_id, "result": result}


@router.delete("/cron/{job_id:int}")
@router.delete("/api/cron/{job_id:int}")
async def remove_cron(request: Request, job_id: int):
    """Remove a cron job and unschedule it."""
    require_admin(request)
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
