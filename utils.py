"""
Meta Platforms Chat Exporter - Utilitários
Funções auxiliares para limpeza, tradução e detecção de tipo de arquivo
"""

import html
import logging
from pathlib import Path

from constants import (
    RE_HTML_TAGS, RE_PAGE_BREAK, RE_MULTIPLE_SPACES,
    TRANSLATIONS, TRANSLATIONS_KEYS_SORTED
)

logger = logging.getLogger(__name__)


def clean_message_body(text: str) -> str:
    """Remove tags HTML e quebras de página do corpo da mensagem"""
    if not text:
        return text
    # Remove tags HTML
    text = RE_HTML_TAGS.sub('', text)
    # Remove texto de quebra de página
    text = RE_PAGE_BREAK.sub('', text)
    # Normaliza espaços
    text = RE_MULTIPLE_SPACES.sub(' ', text)
    return text.strip()


def translate_message(text: str) -> str:
    """Traduz mensagens padrão do inglês para português.
    Usa chaves ordenadas por comprimento decrescente para evitar
    que traduções curtas (ex: 'sent') substituam partes de frases
    mais longas (ex: 'sent a voice message.') antes.
    """
    if not text:
        return text

    # Verificar traduções exatas primeiro
    if text in TRANSLATIONS:
        return TRANSLATIONS[text]

    # Verificar traduções parciais (ordenadas por comprimento decrescente)
    for eng in TRANSLATIONS_KEYS_SORTED:
        if eng in text:
            text = text.replace(eng, TRANSLATIONS[eng])

    return text


def get_file_type(path: str) -> str:
    """Determina tipo de arquivo pela extensão (usa endswith para precisão)"""
    ext = Path(path).suffix.lower()

    # Áudio
    if ext == '.mp3':
        return "audio/mpeg"
    elif ext == '.m4a':
        return "audio/mp4"
    elif ext == '.aac':
        return "audio/aac"
    elif ext == '.wav':
        return "audio/wav"
    elif ext == '.ogg':
        return "audio/ogg"
    # MP4 pode ser vídeo ou áudio (audioclip, voice, audio no nome indica áudio)
    elif ext == '.mp4':
        lower = path.lower()
        if any(x in lower for x in ['audioclip', 'voice', 'audio', 'mensagem_de_voz']):
            return "audio/mpeg"
        return "video/mp4"
    # Imagens
    elif ext in ('.jpg', '.jpeg'):
        return "image/jpeg"
    elif ext == '.png':
        return "image/png"
    elif ext == '.gif':
        return "image/gif"
    elif ext == '.webp':
        return "image/webp"

    return "unknown"
