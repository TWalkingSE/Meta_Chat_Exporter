"""
Meta Platforms Chat Exporter - Media Parser
Parser para seções de Photos, Videos e Archived Stories dos registros da Meta
"""

import html
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from constants import RE_PAGE_BREAK_FULL
from constants import get_timezone_offset
import constants
from models import Photo, Video, Story, ProfileMedia

logger = logging.getLogger(__name__)

# Regex para extrair campos das seções de mídia
RE_MEDIA_ID_FIELD = re.compile(
    r'Id<div class="m"><div>(\d{10,25})<div class="p">', re.DOTALL
)
RE_STORY_ID = re.compile(
    r'<div class="t i"><div class="m"><div>(\d{10,25})<div class="p">', re.DOTALL
)
RE_MEDIA_TIME = re.compile(
    r'(?:Taken|Time)<div class="m"><div>(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)', re.DOTALL
)
RE_MEDIA_PRIVACY = re.compile(
    r'Privacy Setting<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_OWNER = re.compile(
    r'Owner<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_LINKED = re.compile(
    r'Linked Media File:<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_LIKE_COUNT = re.compile(
    r'Like Count<div class="m"><div>(\d+)', re.DOTALL
)
RE_MEDIA_CAPTION_TEXT = re.compile(
    r'Caption<div class="m"><div>.*?Text<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_LOCATION_NAME = re.compile(
    r'Location<div class="m"><div>.*?Name<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_LOCATION_ADDR = re.compile(
    r'Address<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_CAROUSEL = re.compile(
    r'Carousel Id<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_FILTER = re.compile(
    r'Filter<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_PUBLISHED = re.compile(
    r'Is Published<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_SOURCE = re.compile(
    r'Source<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_AI = re.compile(
    r'Ai<div class="m"><div>([^<]+)', re.DOTALL
)
RE_MEDIA_IMG_SRC = re.compile(
    r'<img[^>]+src="([^"]+)"', re.DOTALL
)
RE_MEDIA_VIDEO_SRC = re.compile(
    r'<source\s+src="([^"]+)"\s+type="video/mp4"', re.DOTALL
)

# Para dividir entries: photos/videos usam "Linked Media File:", stories usam ID numérico
RE_LINKED_ENTRY_SPLIT = re.compile(
    r'Linked Media File:<div class="m"><div>[^<]+'
)
RE_STORY_ENTRY_SPLIT = re.compile(
    r'<div class="t i"><div class="m"><div>\d{10,25}<div class="p">'
)


class MediaParser:
    """Parser para seções de Photos, Videos e Archived Stories"""

    def __init__(self, html_path: str, log_callback=None):
        self.html_path = Path(html_path)
        self.base_dir = self.html_path.parent
        self.source_filename = self.html_path.name
        self.log = log_callback or (lambda x: None)

    def parse(self) -> ProfileMedia:
        """Parseia todas as seções de mídia do arquivo HTML"""
        result = ProfileMedia()

        content = self._read_file()
        if content is None:
            return result

        logger.info("Parseando mídias de %s...", self.source_filename)

        # Photos
        photos = self._parse_section(content, 'photos', self._parse_photo_entry, category='Photos')
        result.photos = photos
        if photos:
            self.log(f"📷 {len(photos)} fotos encontradas (Photos)")
            logger.info("Fotos: %d", len(photos))

        # Profile Picture (também são fotos)
        profile_pics = self._parse_section(content, 'profile_picture', self._parse_photo_entry, category='Profile Picture')
        if profile_pics:
            result.photos.extend(profile_pics)
            self.log(f"📷 {len(profile_pics)} fotos encontradas (Profile Picture)")
            logger.info("Profile Pictures: %d", len(profile_pics))

        # Videos
        videos = self._parse_section(content, 'videos', self._parse_video_entry, category='Videos')
        result.videos = videos
        if videos:
            self.log(f"🎬 {len(videos)} vídeos encontrados (Videos)")
            logger.info("Vídeos: %d", len(videos))

        # Live Videos
        live_videos = self._parse_section(content, 'live_videos', self._parse_video_entry, category='Live Videos')
        if live_videos:
            result.videos.extend(live_videos)
            self.log(f"🎬 {len(live_videos)} vídeos encontrados (Live Videos)")
            logger.info("Live Videos: %d", len(live_videos))

        # Archived Live Videos
        archived_live = self._parse_section(content, 'archived_live_videos', self._parse_video_entry, category='Archived Live Videos')
        if archived_live:
            result.videos.extend(archived_live)
            self.log(f"🎬 {len(archived_live)} vídeos encontrados (Archived Live Videos)")
            logger.info("Archived Live Videos: %d", len(archived_live))

        # Archived Stories
        stories = self._parse_section(content, 'archived_stories', self._parse_story_entry, category='Archived Stories')
        result.stories = stories
        if stories:
            self.log(f"📱 {len(stories)} stories encontrados (Archived Stories)")
            logger.info("Stories: %d", len(stories))

        # Unarchived Stories
        unarchived = self._parse_section(content, 'unarchived_stories', self._parse_story_entry, category='Unarchived Stories')
        if unarchived:
            result.stories.extend(unarchived)
            self.log(f"📱 {len(unarchived)} stories encontrados (Unarchived Stories)")
            logger.info("Unarchived Stories: %d", len(unarchived))

        if result.is_empty:
            self.log("ℹ️ Nenhuma mídia de perfil encontrada")
        else:
            self.log(f"✅ Total de mídias do perfil: {result.total}")

        return result

    def _read_file(self) -> Optional[str]:
        """Lê o arquivo HTML com fallback de encoding"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(self.html_path, 'r', encoding=encoding, buffering=1024*1024) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except (PermissionError, OSError) as e:
                logger.error("Erro ao ler %s: %s", self.html_path, e)
                return None
        logger.error("Nenhum encoding funcionou para: %s", self.html_path)
        return None

    def _extract_section(self, content: str, section_name: str) -> Optional[str]:
        """Extrai uma seção pelo id property-<nome>"""
        marker = f'id="property-{section_name}"'
        start = content.find(marker)
        if start == -1:
            return None

        # Encontrar fim da seção (próximo property ou fim)
        end = content.find('id="property-', start + len(marker))
        if end == -1:
            end = len(content)

        section = content[start:end]
        # Limpar page breaks
        section = RE_PAGE_BREAK_FULL.sub('', section)
        return section

    def _split_entries_by_linked(self, section: str) -> List[str]:
        """Divide seção de Photos/Videos usando Linked Media File como âncora"""
        positions = [m.start() for m in RE_LINKED_ENTRY_SPLIT.finditer(section)]
        if not positions:
            return []

        entries = []
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(section)
            entries.append(section[pos:end])
        return entries

    def _split_entries_by_story_id(self, section: str) -> List[str]:
        """Divide seção de Stories usando IDs numéricos"""
        positions = [m.start() for m in RE_STORY_ENTRY_SPLIT.finditer(section)]
        if not positions:
            return []

        entries = []
        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(section)
            entries.append(section[pos:end])
        return entries

    def _parse_section(self, content: str, section_name: str, parser_func, category: str = "") -> list:
        """Parseia uma seção genérica"""
        section = self._extract_section(content, section_name)
        if section is None:
            logger.debug("Seção '%s' não encontrada", section_name)
            return []

        # Verificar se tem registros
        if 'No responsive records' in section:
            logger.debug("Seção '%s': sem registros", section_name)
            return []

        # Todas as seções usam Linked Media File como âncora de split
        entries = self._split_entries_by_linked(section)
        logger.debug("Seção '%s': %d entradas", section_name, len(entries))

        items = []
        for entry_html in entries:
            item = parser_func(entry_html)
            if item:
                if category:
                    item.category = category
                items.append(item)

        return items

    def _parse_timestamp(self, text: str) -> Optional[datetime]:
        """Parseia timestamp e aplica offset de timezone"""
        match = RE_MEDIA_TIME.search(text)
        if match:
            try:
                dt_utc = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S UTC')
                return dt_utc + get_timezone_offset()
            except ValueError:
                pass
        return None

    def _parse_common_media_fields(self, entry_html: str, media_type: str) -> Optional[dict]:
        """Extrai campos compartilhados entre foto e vídeo.

        Retorna dict com todos os campos comuns, ou None se ID ou local_path faltarem.
        """
        match = RE_MEDIA_ID_FIELD.search(entry_html)
        if not match:
            return None
        media_id = match.group(1)

        # Linked media path
        local_path = ""
        match = RE_MEDIA_LINKED.search(entry_html)
        if match:
            local_path = match.group(1).strip()
        else:
            fallback_re = RE_MEDIA_IMG_SRC if media_type == "photo" else RE_MEDIA_VIDEO_SRC
            match = fallback_re.search(entry_html)
            if match:
                local_path = match.group(1).strip()

        if not local_path:
            return None

        # Rejeitar paths com traversal (../)
        if '..' in local_path:
            logger.warning("Path traversal detectado em %s, ignorando: %s", media_type, local_path)
            return None

        taken = self._parse_timestamp(entry_html)

        caption = ""
        match = RE_MEDIA_CAPTION_TEXT.search(entry_html)
        if match:
            caption = html.unescape(match.group(1).strip())

        owner = ""
        match = RE_MEDIA_OWNER.search(entry_html)
        if match:
            owner = match.group(1).strip()

        privacy = ""
        match = RE_MEDIA_PRIVACY.search(entry_html)
        if match:
            privacy = match.group(1).strip()

        like_count = 0
        match = RE_MEDIA_LIKE_COUNT.search(entry_html)
        if match:
            try:
                like_count = int(match.group(1))
            except ValueError:
                pass

        location_name = ""
        match = RE_MEDIA_LOCATION_NAME.search(entry_html)
        if match:
            location_name = match.group(1).strip()

        location_address = ""
        match = RE_MEDIA_LOCATION_ADDR.search(entry_html)
        if match:
            location_address = match.group(1).strip()

        carousel_id = ""
        match = RE_MEDIA_CAROUSEL.search(entry_html)
        if match:
            carousel_id = match.group(1).strip()

        filter_name = ""
        match = RE_MEDIA_FILTER.search(entry_html)
        if match:
            filter_name = match.group(1).strip()

        is_published = ""
        match = RE_MEDIA_PUBLISHED.search(entry_html)
        if match:
            is_published = match.group(1).strip()

        source = ""
        match = RE_MEDIA_SOURCE.search(entry_html)
        if match:
            source = match.group(1).strip()

        return {
            "media_id": media_id,
            "taken": taken,
            "caption": caption,
            "owner": owner,
            "privacy": privacy,
            "local_path": local_path,
            "like_count": like_count,
            "location_name": location_name,
            "location_address": location_address,
            "carousel_id": carousel_id,
            "filter_name": filter_name,
            "is_published": is_published,
            "source": source,
        }

    def _parse_photo_entry(self, entry_html: str) -> Optional[Photo]:
        """Parseia uma entrada de foto"""
        fields = self._parse_common_media_fields(entry_html, "photo")
        if not fields:
            return None

        return Photo(
            photo_id=fields["media_id"],
            taken=fields["taken"],
            caption=fields["caption"],
            owner=fields["owner"],
            privacy=fields["privacy"],
            local_path=fields["local_path"],
            like_count=fields["like_count"],
            location_name=fields["location_name"],
            location_address=fields["location_address"],
            carousel_id=fields["carousel_id"],
            filter_name=fields["filter_name"],
            is_published=fields["is_published"],
            source=fields["source"],
            source_file=self.source_filename
        )

    def _parse_video_entry(self, entry_html: str) -> Optional[Video]:
        """Parseia uma entrada de vídeo"""
        fields = self._parse_common_media_fields(entry_html, "video")
        if not fields:
            return None

        return Video(
            video_id=fields["media_id"],
            taken=fields["taken"],
            caption=fields["caption"],
            owner=fields["owner"],
            privacy=fields["privacy"],
            local_path=fields["local_path"],
            like_count=fields["like_count"],
            location_name=fields["location_name"],
            location_address=fields["location_address"],
            carousel_id=fields["carousel_id"],
            filter_name=fields["filter_name"],
            is_published=fields["is_published"],
            source=fields["source"],
            source_file=self.source_filename
        )

    def _parse_story_entry(self, entry_html: str) -> Optional[Story]:
        """Parseia uma entrada de story"""
        # Extrair story ID: tentar pelo campo numérico ou pelo filename
        story_id = ""
        match = RE_STORY_ID.search(entry_html)
        if match:
            story_id = match.group(1)
        else:
            # Extrair ID do nome do arquivo linked_media/archived_stories_XXXX.ext ou unarchived_stories
            id_match = re.search(r'(?:archived|unarchived)_stories_?(\d+)?', entry_html)
            if id_match and id_match.group(1):
                story_id = id_match.group(1)
            else:
                id_match = re.search(r'stories_.*?(\d+)\.', entry_html)
                if id_match:
                    story_id = id_match.group(1)
        if not story_id:
            return None

        # Linked media path
        local_path = ""
        match = RE_MEDIA_LINKED.search(entry_html)
        if match:
            local_path = match.group(1).strip()

        if not local_path:
            # Fallback: tentar src de video ou img
            match = RE_MEDIA_VIDEO_SRC.search(entry_html)
            if match:
                local_path = match.group(1).strip()
            else:
                match = RE_MEDIA_IMG_SRC.search(entry_html)
                if match:
                    local_path = match.group(1).strip()

        if not local_path:
            return None

        # Rejeitar paths com traversal (../)
        if '..' in local_path:
            logger.warning("Path traversal detectado em story, ignorando: %s", local_path)
            return None

        # Determinar tipo de mídia
        ext = Path(local_path).suffix.lower()
        if ext in ('.mp4', '.mov', '.avi', '.webm'):
            media_type = "video"
        elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic'):
            media_type = "image"
        else:
            media_type = "video" if '<video' in entry_html else "image"

        time = self._parse_timestamp(entry_html)

        owner = ""
        match = RE_MEDIA_OWNER.search(entry_html)
        if match:
            owner = match.group(1).strip()

        privacy = ""
        match = RE_MEDIA_PRIVACY.search(entry_html)
        if match:
            privacy = match.group(1).strip()

        ai_generated = False
        match = RE_MEDIA_AI.search(entry_html)
        if match:
            ai_generated = match.group(1).strip().lower() == 'true'

        return Story(
            story_id=story_id,
            time=time,
            owner=owner,
            privacy=privacy,
            local_path=local_path,
            media_type=media_type,
            ai_generated=ai_generated,
            source_file=self.source_filename
        )
