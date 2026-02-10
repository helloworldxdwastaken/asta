from typing import Any
from app.db import get_db
from app.learn_about import parse_learn_about, parse_duration_only
from app.tasks.scheduler import schedule_learning_job

class LearningService:
    @staticmethod
    async def process_learning(user_id: str, text: str, channel: str, channel_target: str) -> dict[str, Any] | None:
        """
        Process 'learn about' intents or pending learn duration answers.
        Returns context updates or None.
        """
        db = get_db()
        pending_learn = await db.get_pending_learn_about(user_id)
        
        # 1. Answer to "how long?"
        if pending_learn and parse_duration_only(text) is not None:
            duration_minutes = parse_duration_only(text)
            topic = pending_learn["topic"]
            await db.clear_pending_learn_about(user_id)
            job_id = schedule_learning_job(
                user_id, topic, duration_minutes,
                channel=channel, channel_target=channel_target or "web",
            )
            return {
                "learn_about_started": {"topic": topic, "duration_minutes": duration_minutes, "job_id": job_id},
                "is_learning": True
            }
            
        # 2. New learn intent
        learn_intent = parse_learn_about(text)
        if learn_intent:
            if learn_intent.get("ask_duration"):
                await db.set_pending_learn_about(user_id, learn_intent["topic"])
                return {
                    "learn_about_ask_duration": learn_intent["topic"],
                    "is_learning": True
                }
            else:
                job_id = schedule_learning_job(
                    user_id,
                    learn_intent["topic"],
                    learn_intent["duration_minutes"],
                    channel=channel,
                    channel_target=channel_target or "web",
                )
                return {
                    "learn_about_started": {
                        "topic": learn_intent["topic"],
                        "duration_minutes": learn_intent["duration_minutes"],
                        "job_id": job_id,
                    },
                    "is_learning": True
                }
        return None
