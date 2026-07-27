"""
Meta Platforms Chat Exporter - Data Models
Dataclasses para representação de mensagens, anexos, threads e mídias de perfil
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


class Participant(NamedTuple):
    """Participante de uma conversa (username, plataforma, user_id)"""

    username: str
    platform: str = ""
    user_id: str = ""


@dataclass
class Attachment:
    filename: str
    file_type: str
    size: int = 0
    url: str = ""
    local_path: str = ""


@dataclass
class Message:
    author: str
    author_id: str
    platform: str
    sent: datetime | None = None
    body: str = ""
    disappearing: bool = False
    disappearing_duration: str = ""
    attachments: list["Attachment"] = field(default_factory=list)
    share_url: str | None = None
    share_text: str | None = None
    is_call: bool = False
    call_type: str = ""
    call_duration: int = 0
    call_missed: bool = False
    removed_by_sender: bool = False
    source_file: str = ""
    # Novos campos - Melhoria #2/#4
    is_reaction: bool = False
    subscription_event: str = ""  # "subscribe", "unsubscribe", ou ""
    subscription_users: list[str] = field(default_factory=list)
    has_payment: bool = False
    is_edited: bool = False


@dataclass
class Thread:
    thread_id: str
    thread_name: str = ""
    participants: list[Participant] = field(default_factory=list)
    past_participants: list[Participant] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    ai_enabled: bool = False
    read_receipts: str = "Enabled"
    base_dir: Path | None = None


@dataclass
class Photo:
    photo_id: str
    taken: datetime | None = None
    caption: str = ""
    owner: str = ""
    privacy: str = ""
    local_path: str = ""
    url: str = ""
    like_count: int = 0
    location_name: str = ""
    location_address: str = ""
    carousel_id: str = ""
    filter_name: str = ""
    is_published: str = ""
    source: str = ""
    source_file: str = ""
    category: str = ""


@dataclass
class Video:
    video_id: str
    taken: datetime | None = None
    caption: str = ""
    owner: str = ""
    privacy: str = ""
    local_path: str = ""
    url: str = ""
    like_count: int = 0
    location_name: str = ""
    location_address: str = ""
    carousel_id: str = ""
    filter_name: str = ""
    is_published: str = ""
    source: str = ""
    source_file: str = ""
    category: str = ""


@dataclass
class Story:
    story_id: str
    time: datetime | None = None
    owner: str = ""
    privacy: str = ""
    local_path: str = ""
    media_type: str = ""  # "image" ou "video"
    ai_generated: bool = False
    source_file: str = ""
    category: str = ""


@dataclass
class GenericRecord:
    entries: list[dict[str, str]] = field(default_factory=list)


@dataclass
class GenericCategory:
    category_id: str
    category_name: str
    records: list[GenericRecord] = field(default_factory=list)


@dataclass
class ProfileMedia:
    """Container para todas as mídias e categorias extras do perfil"""

    photos: list[Photo] = field(default_factory=list)
    videos: list[Video] = field(default_factory=list)
    stories: list[Story] = field(default_factory=list)
    generic_categories: list[GenericCategory] = field(default_factory=list)

    @property
    def media_total(self) -> int:
        """Total de mídias exibíveis (fotos, vídeos, stories) — sem categorias genéricas"""
        return len(self.photos) + len(self.videos) + len(self.stories)

    @property
    def total(self) -> int:
        return self.media_total + sum(len(c.records) for c in self.generic_categories)

    @property
    def has_media(self) -> bool:
        """True se há fotos, vídeos ou stories"""
        return self.media_total > 0

    @property
    def is_empty(self) -> bool:
        return self.total == 0
