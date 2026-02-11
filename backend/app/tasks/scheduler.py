"""APScheduler: learning jobs, reminders."""
from __future__ import annotations
import asyncio
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

# Varied search queries so we don't repeat the same search; fills different angles.
LEARN_QUERY_TEMPLATES = [
    "what is {topic}",
    "{topic} overview",
    "{topic} tutorial",
    "{topic} best practices",
    "{topic} getting started",
    "{topic} examples",
    "{topic} documentation",
    "how does {topic} work",
    "{topic} guide",
    "{topic} tips",
    "{topic} vs alternatives",
    "{topic} comparison",
    "{topic} advanced",
    "{topic} common issues",
    "{topic} use cases",
]


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def _run_learning_job_sync(
    job_id: str,
    user_id: str,
    topic: str,
    duration_minutes: int,
    channel: str,
    channel_target: str,
) -> None:
    """Run learning loop for duration_minutes: varied web searches, add to RAG, then notify. Runs in scheduler thread."""
    import asyncio
    from app.rag.service import get_rag
    from app.search_web import search_web
    from app.reminders import send_notification

    end_time = time.time() + max(1, duration_minutes) * 60
    rag = get_rag()
    templates = LEARN_QUERY_TEMPLATES
    idx = 0
    added = 0
    try:
        while time.time() < end_time:
            query = templates[idx % len(templates)].format(topic=topic).strip()
            if not query:
                idx += 1
                time.sleep(15)
                continue
            try:
                results, _ = search_web(query, max_results=5)
                for r in (results or []):
                    snippet = (r.get("snippet") or "").strip()
                    if snippet and len(snippet) > 80:
                        doc_id = f"{job_id}_{idx}_{added}"
                        async def _add_chunk():
                            r = get_rag()
                            await r.add(topic, snippet[:4000], doc_id=doc_id)
                        asyncio.run(_add_chunk())
                        added += 1
            except Exception as e:
                logger.warning("Learn search/add failed for %s: %s", query[:50], e)
            idx += 1
            time.sleep(20)  # avoid rate limit
        msg = f"Done learning about {topic} for {duration_minutes} min. You can ask me anything about it."
    except Exception as e:
        logger.exception("Learning job failed: %s", e)
        msg = f"Learning about {topic} stopped (error). You can still ask me what I've learned so far."
    try:
        # Give DB a moment to settle/commit so the user can query immediately
        time.sleep(2)
        asyncio.run(send_notification(channel, channel_target, msg))
    except Exception as e:
        logger.warning("Could not send learning-done notification: %s", e)


def schedule_learning_job(
    user_id: str,
    topic: str,
    duration_minutes: int,
    channel: str = "web",
    channel_target: str = "",
    sources: list[str] | None = None,
) -> str:
    """Schedule a background job that learns about topic for duration_minutes (web search + RAG), then notifies. Returns job_id."""
    sch = get_scheduler()
    job_id = f"learn_{user_id}_{topic.replace(' ', '_')[:30]}_{int(time.time())}"
    if sources:
        # Optional: ingest provided text immediately
        async def _add_sources():
            from app.rag.service import get_rag
            rag = get_rag()
            for s in sources:
                if (s or "").strip():
                    await rag.add(topic, (s or "")[:5000], doc_id=f"{job_id}_src")
        try:
            asyncio.run(_add_sources())
        except Exception as e:
            logger.warning("Could not add provided sources to RAG: %s", e)
    from datetime import datetime, timezone
    sch.add_job(
        _run_learning_job_sync,
        DateTrigger(run_date=datetime.now(timezone.utc)),
        id=job_id,
        max_instances=1,
        args=[job_id, user_id, topic, duration_minutes, channel, channel_target],
        replace_existing=True,
    )
    return job_id
