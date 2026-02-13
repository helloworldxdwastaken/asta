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

# Instantiate singleton skills
_ALL_SKILLS: list[Skill] = [
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

_SKILLS_BY_NAME = {s.name: s for s in _ALL_SKILLS}

def get_all_skills() -> list[Skill]:
    return _ALL_SKILLS

def get_skill_by_name(name: str) -> Skill | None:
    return _SKILLS_BY_NAME.get(name)
