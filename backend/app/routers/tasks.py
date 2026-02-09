"""Scheduled tasks and learning jobs."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.db import get_db
from app.tasks.scheduler import schedule_learning_job

router = APIRouter()


class LearnJobIn(BaseModel):
    topic: str
    duration_minutes: int = 120
    sources: list[str] = []
    user_id: str = "default"
    channel: str = "web"
    channel_target: str = ""


@router.post("/tasks/learn")
async def start_learning_job(body: LearnJobIn):
    """Start a 'learn topic for X minutes' job. Notifies on the given channel when done. Sources can be URLs or text snippets."""
    job_id = schedule_learning_job(
        body.user_id,
        body.topic,
        body.duration_minutes,
        channel=body.channel,
        channel_target=body.channel_target or "",
        sources=body.sources or None,
    )
    return {"job_id": job_id, "topic": body.topic, "duration_minutes": body.duration_minutes}
