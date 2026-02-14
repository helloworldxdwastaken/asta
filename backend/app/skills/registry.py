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
    out: list[Skill] = list(_BUILTIN_SKILLS)
    for r in discover_workspace_skills_runtime():
        out.append(MarkdownSkill(r))
    return out


def get_skill_by_name(name: str) -> Skill | None:
    for s in get_all_skills():
        if s.name == name:
            return s
    return None
