import logging
import time

from app.lib.skill import Skill
from app.skills.server_status import ServerStatusSkill
from app.skills.time import TimeSkill
from app.skills.weather import WeatherSkill
from app.skills.files import FilesSkill
from app.skills.rag import RagSkill
from app.skills.web import GoogleSearchSkill
from app.skills.spotify import SpotifySkill
from app.skills.reminders import RemindersSkill
from app.skills.self_awareness import SelfAwarenessSkill
from app.skills.learning import LearningSkill
from app.skills.audio_notes import AudioNotesSkill
from app.skills.silly_gif import SillyGifSkill
from app.skills.markdown_skill import MarkdownSkill
from app.skills.vercel import VercelSkill
from app.skills.github import GitHubSkill
from app.skills.gog import GoogleWorkspaceSkill
from app.skills.research_skill import ResearchSkill
from app.workspace import discover_workspace_skills_runtime

logger = logging.getLogger(__name__)

# Cache for get_all_skills() — avoids re-scanning filesystem on every request
_skills_cache: list[Skill] | None = None
_skills_cache_ts: float = 0.0
_SKILLS_CACHE_TTL = 30.0  # seconds

# Built-in skills (singletons)
_BUILTIN_SKILLS: list[Skill] = [
    ServerStatusSkill(),
    TimeSkill(),
    WeatherSkill(),
    FilesSkill(),
    RagSkill(),
    GoogleSearchSkill(),
    SpotifySkill(),
    RemindersSkill(),
    SelfAwarenessSkill(),
    LearningSkill(),
    AudioNotesSkill(),
    SillyGifSkill(),
    VercelSkill(),
    GitHubSkill(),
    GoogleWorkspaceSkill(),
    ResearchSkill(),
]


def get_all_skills() -> list[Skill]:
    """All skills: built-in + OpenClaw-style workspace/skills/*/SKILL.md.
    Results are cached for _SKILLS_CACHE_TTL seconds to avoid repeated filesystem scans."""
    global _skills_cache, _skills_cache_ts
    now = time.monotonic()
    if _skills_cache is not None and (now - _skills_cache_ts) < _SKILLS_CACHE_TTL:
        return _skills_cache

    out: list[Skill] = []
    seen: set[str] = set()
    for skill in _BUILTIN_SKILLS:
        sid = str(getattr(skill, "name", "") or "").strip().lower()
        if not sid:
            continue
        if sid in seen:
            logger.warning("Duplicate built-in skill id '%s' ignored.", sid)
            continue
        seen.add(sid)
        out.append(skill)
    for r in discover_workspace_skills_runtime():
        sid = (r.name or "").strip().lower()
        if not sid:
            continue
        if sid in seen:
            logger.warning(
                "Workspace skill '%s' ignored because id collides with an existing skill.",
                sid,
            )
            continue
        seen.add(sid)
        out.append(MarkdownSkill(r))

    _skills_cache = out
    _skills_cache_ts = now
    return out


def get_skill_by_name(name: str) -> Skill | None:
    for s in get_all_skills():
        if s.name == name:
            return s
    return None
