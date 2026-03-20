import logging
import shlex

logger = logging.getLogger(__name__)


def _subagents_help_text() -> str:
    return (
        "Subagents commands:\n"
        "- /subagents list [limit]\n"
        "- /subagents spawn <task>\n"
        "- /subagents info <runId> [limit]\n"
        "- /subagents send <runId> <message> [--wait <seconds>]\n"
        "- /subagents stop <runId>\n"
        "- /subagents help"
    )


def _learn_help_text() -> str:
    return (
        "Learn commands:\n"
        "- /learn <topic> - Save information about a topic to memory\n"
        "- /learn list - Show saved topics\n"
        "- /learn delete <topic> - Delete a saved topic\n"
        "- /learn help - Show this help"
    )


def _parse_learn_command(text: str) -> tuple[str, list[str]] | None:
    """Parse /learn command. Returns (action, args) or None if not a learn command."""
    raw = (text or "").strip()
    if not raw.lower().startswith("/learn"):
        return None
    rest = raw[len("/learn"):].strip()
    if not rest:
        return "help", []
    try:
        tokens = shlex.split(rest)
    except Exception:
        tokens = rest.split()
    if not tokens:
        return "help", []
    first = (tokens[0] or "").strip().lower()
    if first in ("help", "h", "?", "list", "ls", "delete", "remove", "rm"):
        return first, [t for t in tokens[1:] if isinstance(t, str)]
    # Default path: /learn <topic...>
    return "learn", [t for t in tokens if isinstance(t, str)]


async def _handle_learn_command(
    *,
    user_id: str,
    text: str,
    channel: str,
    channel_target: str,
) -> str | None:
    """Handle /learn command - save information to memory/RAG."""
    parsed = _parse_learn_command(text)
    if not parsed:
        return None
    action, args = parsed

    if action in ("help", "h", "?"):
        return _learn_help_text()

    if action in ("list", "ls"):
        from app.rag.service import get_rag
        try:
            topics = get_rag().list_topics()
            if not topics:
                return "You haven't saved any topics yet. Use /learn <topic> to save information."
            lines = [f"You have {len(topics)} saved topic(s):"]
            for i, topic in enumerate(topics[:20], 1):
                if isinstance(topic, dict):
                    name = topic.get("topic", "Unknown")
                    lines.append(f"{i}. {name}")
                else:
                    lines.append(f"{i}. {topic}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Could not list learned topics: %s", e)
            return "Could not list saved topics."

    if action in ("delete", "remove", "rm"):
        # Delete a saved topic
        if not args:
            return "Usage: /learn delete <topic_name>"
        topic_name = " ".join(args).strip()
        if not topic_name:
            return "Please specify a topic to delete."
        from app.rag.service import get_rag
        try:
            deleted = int(get_rag().delete_topic(topic_name))
            if deleted > 0:
                return f"Deleted topic: {topic_name}"
            return f"Could not delete topic '{topic_name}'. It may not exist."
        except Exception as e:
            logger.warning("Could not delete learned topic: %s", e)
            return f"Could not delete topic '{topic_name}'."

    # Default: learn/save a topic - use LearningService
    topic_text = " ".join(args).strip()
    if not topic_text:
        return _learn_help_text()

    # Process via LearningService to save to RAG
    try:
        from app.services.learning_service import LearningService
        result = await LearningService.process_learning(
            user_id=user_id,
            text=f"learn about {topic_text}",
            channel=channel,
            channel_target=channel_target,
        )
        if result and result.get("is_learning"):
            return f"Saved to memory: '{topic_text}'. I'll remember this."
    except Exception as e:
        logger.warning("Could not learn topic: %s", e)

    # Fallback response
    return f"Saved to memory: '{topic_text}'. I'll remember this."
