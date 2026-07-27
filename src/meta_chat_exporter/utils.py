"""
Meta Platforms Chat Exporter - Utilitários
Funções auxiliares para limpeza, tradução e detecção de tipo de arquivo
"""

import html
import logging
from pathlib import Path

from meta_chat_exporter.constants import (
    RE_HTML_TAGS,
    RE_MULTIPLE_SPACES,
    RE_PAGE_BREAK,
    TRANSLATIONS,
    TRANSLATIONS_KEYS_SORTED,
)

logger = logging.getLogger(__name__)


def escape_html(value: object) -> str:
    """Escapa <, >, & (e aspas) para entidades HTML. Converte não-str para str.

    Ponto único de escape de HTML reutilizado pelos renderizadores e geradores,
    garantindo uso consistente de ``html.escape``. Valores ``None`` viram string
    vazia e valores não-str são convertidos com ``str`` antes do escape.
    """
    return html.escape("" if value is None else str(value), quote=True)


def clean_message_body(text: str) -> str:
    """Remove tags HTML e quebras de página do corpo da mensagem"""
    if not text:
        return text
    # Remove tags HTML
    text = RE_HTML_TAGS.sub("", text)
    # Remove texto de quebra de página
    text = RE_PAGE_BREAK.sub("", text)
    # Normaliza espaços
    text = RE_MULTIPLE_SPACES.sub(" ", text)
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
    if ext == ".mp3":
        return "audio/mpeg"
    elif ext == ".m4a":
        return "audio/mp4"
    elif ext == ".aac":
        return "audio/aac"
    elif ext == ".wav":
        return "audio/wav"
    elif ext == ".ogg":
        return "audio/ogg"
    # MP4 pode ser vídeo ou áudio (audioclip, voice, audio no nome indica áudio)
    elif ext == ".mp4":
        lower = path.lower()
        if any(x in lower for x in ["audioclip", "voice", "audio", "mensagem_de_voz"]):
            return "audio/mpeg"
        return "video/mp4"
    # Imagens
    elif ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".gif":
        return "image/gif"
    elif ext == ".webp":
        return "image/webp"

    return "unknown"


_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})


def is_safe_url(url: str) -> bool:
    """Retorna True se ``url`` usa um scheme permitido para links no HTML exportado.

    Aceita apenas ``http``, ``https`` e ``mailto``. Rejeita schemes perigosos
    como ``javascript:``, ``data:``, ``vbscript:`` e URLs vazias.
    """
    if not url or not isinstance(url, str):
        return False
    stripped = url.strip()
    if not stripped or stripped.startswith("#"):
        return False
    # Scheme relativo (//host) ou path relativo sem scheme: tratar como inseguro
    # no contexto de share_url (sempre esperamos URL absoluta de compartilhamento).
    if ":" not in stripped.split("/", 1)[0]:
        return False
    scheme = stripped.split(":", 1)[0].lower()
    return scheme in _SAFE_URL_SCHEMES


def is_safe_relative_path(path: str) -> bool:
    """Valida que ``path`` é um caminho relativo seguro, sem escapar do diretório.

    Rejeita: caminhos vazios, absolutos (POSIX ``/...`` ou com letra de drive no
    Windows, ``C:\\...``), UNC (``\\\\server``) e qualquer componente ``..``.
    Mais robusto que ``".." in path`` (não tem falso-positivo com nomes como
    ``foto..jpg`` e bloqueia caminhos absolutos que aquela checagem deixava passar).
    """
    if not path:
        return False

    normalized = path.replace("\\", "/")

    # Caminho absoluto POSIX ou UNC
    if normalized.startswith("/"):
        return False

    # Drive do Windows (ex.: "C:/..." ou "C:foo")
    if len(path) >= 2 and path[1] == ":":
        return False

    # Qualquer componente de traversal
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    return ".." not in parts
