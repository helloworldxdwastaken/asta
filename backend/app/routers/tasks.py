"""Scheduled tasks and learning jobs."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.auth_utils import get_current_user_id, require_admin
from app.db import get_db
from app.tasks.scheduler import schedule_learning_job

router = APIRouter()


class LearnJobIn(BaseModel):
    topic: str
    duration_minutes: int = 120
    sources: list[str] = []
    channel: str = "web"
    channel_target: str = ""


@router.post("/tasks/learn")
async def start_learning_job(request: Request, body: LearnJobIn):
    """Start a 'learn topic for X minutes' job. Notifies on the given channel when done. Sources can be URLs or text snippets."""
    require_admin(request)
    user_id = get_current_user_id(request)
    job_id = schedule_learning_job(
        user_id,
        body.topic,
        body.duration_minutes,
        channel=body.channel,
        channel_target=body.channel_target or "",
        sources=body.sources or None,
    )
    return {"job_id": job_id, "topic": body.topic, "duration_minutes": body.duration_minutes}
