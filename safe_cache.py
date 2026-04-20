"""
Meta Platforms Chat Exporter - Cache Seguro
Serialização JSON segura para cache de dados parseados.
Substitui pickle para evitar riscos de execução de código arbitrário.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import (
    Attachment, Message, Thread, Participant,
    Photo, Video, Story, ProfileMedia
)

logger = logging.getLogger(__name__)


class CacheEncoder(json.JSONEncoder):
    """Encoder JSON customizado para objetos do projeto"""

    def default(self, obj):
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        if isinstance(obj, Path):
            return {"__path__": str(obj)}
        if isinstance(obj, Participant):
            return {"__participant__": list(obj)}
        if isinstance(obj, Attachment):
            return {
                "__attachment__": True,
                "filename": obj.filename,
                "file_type": obj.file_type,
                "size": obj.size,
                "url": obj.url,
                "local_path": obj.local_path,
            }
        if isinstance(obj, Message):
            return {
                "__message__": True,
                "author": obj.author,
                "author_id": obj.author_id,
                "platform": obj.platform,
                "sent": obj.sent,
                "body": obj.body,
                "disappearing": obj.disappearing,
                "disappearing_duration": obj.disappearing_duration,
                "attachments": obj.attachments,
                "share_url": obj.share_url,
                "share_text": obj.share_text,
                "is_call": obj.is_call,
                "call_type": obj.call_type,
                "call_duration": obj.call_duration,
                "call_missed": obj.call_missed,
                "removed_by_sender": obj.removed_by_sender,
                "source_file": obj.source_file,
                "is_reaction": obj.is_reaction,
                "subscription_event": obj.subscription_event,
                "subscription_users": obj.subscription_users,
                "has_payment": obj.has_payment,
            }
        if isinstance(obj, Thread):
            return {
                "__thread__": True,
                "thread_id": obj.thread_id,
                "thread_name": obj.thread_name,
                "participants": obj.participants,
                "past_participants": obj.past_participants,
                "messages": obj.messages,
                "ai_enabled": obj.ai_enabled,
                "read_receipts": obj.read_receipts,
                "base_dir": obj.base_dir,
            }
        if isinstance(obj, Photo):
            return {
                "__photo__": True,
                "photo_id": obj.photo_id,
                "taken": obj.taken,
                "caption": obj.caption,
                "owner": obj.owner,
                "privacy": obj.privacy,
                "local_path": obj.local_path,
                "url": obj.url,
                "like_count": obj.like_count,
                "location_name": obj.location_name,
                "location_address": obj.location_address,
                "carousel_id": obj.carousel_id,
                "filter_name": obj.filter_name,
                "is_published": obj.is_published,
                "source": obj.source,
                "source_file": obj.source_file,
                "category": obj.category,
            }
        if isinstance(obj, Video):
            return {
                "__video__": True,
                "video_id": obj.video_id,
                "taken": obj.taken,
                "caption": obj.caption,
                "owner": obj.owner,
                "privacy": obj.privacy,
                "local_path": obj.local_path,
                "url": obj.url,
                "like_count": obj.like_count,
                "location_name": obj.location_name,
                "location_address": obj.location_address,
                "carousel_id": obj.carousel_id,
                "filter_name": obj.filter_name,
                "is_published": obj.is_published,
                "source": obj.source,
                "source_file": obj.source_file,
                "category": obj.category,
            }
        if isinstance(obj, Story):
            return {
                "__story__": True,
                "story_id": obj.story_id,
                "time": obj.time,
                "owner": obj.owner,
                "privacy": obj.privacy,
                "local_path": obj.local_path,
                "media_type": obj.media_type,
                "ai_generated": obj.ai_generated,
                "source_file": obj.source_file,
                "category": obj.category,
            }
        if isinstance(obj, ProfileMedia):
            return {
                "__profile_media__": True,
                "photos": obj.photos,
                "videos": obj.videos,
                "stories": obj.stories,
            }
        return super().default(obj)


# Marcadores permitidos para desserialização segura
_ALLOWED_MARKERS = frozenset({
    "__datetime__", "__path__", "__participant__", "__attachment__",
    "__message__", "__thread__", "__photo__", "__video__",
    "__story__", "__profile_media__",
})


def _decode_object(obj: dict) -> Any:
    """Decodifica objetos JSON de volta para objetos Python.

    Apenas marcadores conhecidos são aceitos. Marcadores desconhecidos
    são ignorados e o dict é retornado sem conversão.
    """
    # Verificar se há marcadores desconhecidos (possível cache adulterado)
    obj_markers = [k for k in obj if k.startswith("__") and k.endswith("__")]
    for marker in obj_markers:
        if marker not in _ALLOWED_MARKERS:
            logger.warning("Marcador desconhecido no cache ignorado: %s", marker)
            return obj

    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    if "__path__" in obj:
        return Path(obj["__path__"])
    if "__participant__" in obj:
        data = obj["__participant__"]
        return Participant(*data)
    if "__attachment__" in obj:
        return Attachment(
            filename=obj["filename"],
            file_type=obj["file_type"],
            size=obj.get("size", 0),
            url=obj.get("url", ""),
            local_path=obj.get("local_path", ""),
        )
    if "__message__" in obj:
        return Message(
            author=obj["author"],
            author_id=obj["author_id"],
            platform=obj["platform"],
            sent=obj.get("sent"),
            body=obj.get("body", ""),
            disappearing=obj.get("disappearing", False),
            disappearing_duration=obj.get("disappearing_duration", ""),
            attachments=obj.get("attachments", []),
            share_url=obj.get("share_url"),
            share_text=obj.get("share_text"),
            is_call=obj.get("is_call", False),
            call_type=obj.get("call_type", ""),
            call_duration=obj.get("call_duration", 0),
            call_missed=obj.get("call_missed", False),
            removed_by_sender=obj.get("removed_by_sender", False),
            source_file=obj.get("source_file", ""),
            is_reaction=obj.get("is_reaction", False),
            subscription_event=obj.get("subscription_event", ""),
            subscription_users=obj.get("subscription_users", []),
            has_payment=obj.get("has_payment", False),
        )
    if "__thread__" in obj:
        return Thread(
            thread_id=obj["thread_id"],
            thread_name=obj.get("thread_name", ""),
            participants=obj.get("participants", []),
            past_participants=obj.get("past_participants", []),
            messages=obj.get("messages", []),
            ai_enabled=obj.get("ai_enabled", False),
            read_receipts=obj.get("read_receipts", "Enabled"),
            base_dir=obj.get("base_dir"),
        )
    if "__photo__" in obj:
        return Photo(
            photo_id=obj["photo_id"],
            taken=obj.get("taken"),
            caption=obj.get("caption", ""),
            owner=obj.get("owner", ""),
            privacy=obj.get("privacy", ""),
            local_path=obj.get("local_path", ""),
            url=obj.get("url", ""),
            like_count=obj.get("like_count", 0),
            location_name=obj.get("location_name", ""),
            location_address=obj.get("location_address", ""),
            carousel_id=obj.get("carousel_id", ""),
            filter_name=obj.get("filter_name", ""),
            is_published=obj.get("is_published", ""),
            source=obj.get("source", ""),
            source_file=obj.get("source_file", ""),
            category=obj.get("category", ""),
        )
    if "__video__" in obj:
        return Video(
            video_id=obj["video_id"],
            taken=obj.get("taken"),
            caption=obj.get("caption", ""),
            owner=obj.get("owner", ""),
            privacy=obj.get("privacy", ""),
            local_path=obj.get("local_path", ""),
            url=obj.get("url", ""),
            like_count=obj.get("like_count", 0),
            location_name=obj.get("location_name", ""),
            location_address=obj.get("location_address", ""),
            carousel_id=obj.get("carousel_id", ""),
            filter_name=obj.get("filter_name", ""),
            is_published=obj.get("is_published", ""),
            source=obj.get("source", ""),
            source_file=obj.get("source_file", ""),
            category=obj.get("category", ""),
        )
    if "__story__" in obj:
        return Story(
            story_id=obj["story_id"],
            time=obj.get("time"),
            owner=obj.get("owner", ""),
            privacy=obj.get("privacy", ""),
            local_path=obj.get("local_path", ""),
            media_type=obj.get("media_type", ""),
            ai_generated=obj.get("ai_generated", False),
            source_file=obj.get("source_file", ""),
            category=obj.get("category", ""),
        )
    if "__profile_media__" in obj:
        return ProfileMedia(
            photos=obj.get("photos", []),
            videos=obj.get("videos", []),
            stories=obj.get("stories", []),
        )
    return obj


def save_cache(filepath: Path, data: dict) -> None:
    """Salva dados no cache usando JSON seguro"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=CacheEncoder, ensure_ascii=False)


def load_cache(filepath: Path) -> Optional[dict]:
    """Carrega dados do cache usando JSON seguro"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f, object_hook=_decode_object)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Cache corrompido, será ignorado: %s", e)
        return None
    except Exception as e:
        logger.warning("Erro ao ler cache: %s", e)
        return None
