import uuid
from unittest.mock import patch

import pytest

from app.db import get_db
from app.learn_about import parse_learn_about
from app.services.learning_service import LearningService


def test_parse_learn_about_supports_aliases_with_duration():
    parsed = parse_learn_about("become an expert on rust async for 45 min")
    assert parsed == {
        "topic": "rust async",
        "duration_minutes": 45,
        "ask_duration": False,
    }

    parsed = parse_learn_about("can you research graph databases for 2 hours?")
    assert parsed == {
        "topic": "graph databases",
        "duration_minutes": 120,
        "ask_duration": False,
    }

    parsed = parse_learn_about("become expert on retrieval systems for 25 min")
    assert parsed == {
        "topic": "retrieval systems",
        "duration_minutes": 25,
        "ask_duration": False,
    }


def test_parse_learn_about_supports_aliases_without_duration():
    parsed = parse_learn_about("please study kubernetes")
    assert parsed == {
        "topic": "kubernetes",
        "ask_duration": True,
    }

    parsed = parse_learn_about("learn about Next.js")
    assert parsed == {
        "topic": "Next.js",
        "ask_duration": True,
    }


def test_parse_learn_about_ignores_non_command_phrasing():
    assert parse_learn_about("I need to study for finals") is None
    assert parse_learn_about("We did research last week") is None


@pytest.mark.asyncio
async def test_learning_service_alias_with_duration_schedules_job():
    user_id = f"test-learn-{uuid.uuid4().hex[:8]}"
    db = get_db()
    await db.connect()
    await db.clear_pending_learn_about(user_id)

    with patch("app.services.learning_service.schedule_learning_job", return_value="job_alias_1") as sched:
        result = await LearningService.process_learning(
            user_id,
            "can you research graph databases for 30 minutes?",
            "telegram",
            "12345",
        )

    assert result == {
        "learn_about_started": {
            "topic": "graph databases",
            "duration_minutes": 30,
            "job_id": "job_alias_1",
        },
        "is_learning": True,
    }
    sched.assert_called_once_with(
        user_id,
        "graph databases",
        30,
        channel="telegram",
        channel_target="12345",
    )
    assert await db.get_pending_learn_about(user_id) is None


@pytest.mark.asyncio
async def test_learning_service_alias_topic_only_then_duration_reply_schedules_job():
    user_id = f"test-learn-{uuid.uuid4().hex[:8]}"
    db = get_db()
    await db.connect()
    await db.clear_pending_learn_about(user_id)

    first = await LearningService.process_learning(
        user_id,
        "please become an expert on rust async",
        "telegram",
        "999",
    )
    assert first == {
        "learn_about_ask_duration": "rust async",
        "is_learning": True,
    }

    with patch("app.services.learning_service.schedule_learning_job", return_value="job_alias_2") as sched:
        second = await LearningService.process_learning(
            user_id,
            "2 hours",
            "telegram",
            "999",
        )

    assert second == {
        "learn_about_started": {
            "topic": "rust async",
            "duration_minutes": 120,
            "job_id": "job_alias_2",
        },
        "is_learning": True,
    }
    sched.assert_called_once_with(
        user_id,
        "rust async",
        120,
        channel="telegram",
        channel_target="999",
    )
    assert await db.get_pending_learn_about(user_id) is None
