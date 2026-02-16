import logging

from app.lib.skill import Skill
from app.skills.server_status import ServerStatusSkill
from app.skills.time import TimeSkill
from app.skills.weather import WeatherSkill
from app.skills.files import FilesSkill
from app.skills.drive import DriveSkill
from app.skills.rag import RagSkill
from app.skills.web import GoogleSearchSkill
from app.skills.spotify import SpotifySkill
from app.skills.lyrics import LyricsSkill
from app.skills.reminders import RemindersSkill
from app.skills.self_awareness import SelfAwarenessSkill
from app.skills.learning import LearningSkill
from app.skills.audio_notes import AudioNotesSkill
from app.skills.silly_gif import SillyGifSkill
from app.skills.markdown_skill import MarkdownSkill
from app.workspace import discover_workspace_skills_runtime

logger = logging.getLogger(__name__)

# Built-in skills (singletons)
_BUILTIN_SKILLS: list[Skill] = [
    ServerStatusSkill(),
    TimeSkill(),
    WeatherSkill(),
    FilesSkill(),
    DriveSkill(),
    RagSkill(),
    GoogleSearchSkill(),
    SpotifySkill(),
    LyricsSkill(),
    RemindersSkill(),
    SelfAwarenessSkill(),
    LearningSkill(),
    AudioNotesSkill(),
    SillyGifSkill(),
]


def get_all_skills() -> list[Skill]:
    """All skills: built-in + OpenClaw-style workspace/skills/*/SKILL.md."""
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
    return out


def get_skill_by_name(name: str) -> Skill | None:
    for s in get_all_skills():
        if s.name == name:
            return s
    return None
