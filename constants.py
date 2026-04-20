"""
Meta Platforms Chat Exporter - Constantes
Regex pré-compilados, traduções e configurações
"""

import re
import threading
from datetime import timedelta

# ============================================================================
# TIMEZONE (Thread-safe)
# ============================================================================
# Offset do fuso horário para conversão de UTC
# Padrão: UTC-3 (Horário de Brasília)
# Acesso thread-safe via get/set_timezone_offset()

_timezone_lock = threading.Lock()
_timezone_offset = timedelta(hours=-3)


def get_timezone_offset() -> timedelta:
    """Retorna o offset de timezone atual (thread-safe)"""
    with _timezone_lock:
        return _timezone_offset


def set_timezone_offset(offset: timedelta) -> None:
    """Define o offset de timezone (thread-safe)"""
    global _timezone_offset
    with _timezone_lock:
        _timezone_offset = offset


# Mantém compatibilidade com código legado que acessa TIMEZONE_OFFSET diretamente
# ATENÇÃO: Esta variável NÃO é atualizada por set_timezone_offset().
# Novo código deve usar get_timezone_offset() / set_timezone_offset()
TIMEZONE_OFFSET = _timezone_offset

# ============================================================================
# MESES EM PORTUGUÊS
# ============================================================================

MONTHS = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]

# ============================================================================
# REGEX PRÉ-COMPILADOS (otimização)
# ============================================================================

RE_THREAD = re.compile(r'Thread<div class="m"><div>[^(]*\((\d+)\)')
RE_ACCOUNT_ID = re.compile(r'Account Identifier<div class="m"><div>([^<]+)')
RE_TARGET = re.compile(r'Target<div class="m"><div>(\d+)')
RE_PARTICIPANTS = re.compile(
    r'Current Participants<div class="m"><div>(.*?)(?=<div class="t o">|<div class="p"></div><div class="t o">)',
    re.DOTALL
)
RE_USERNAME = re.compile(r'([a-zA-Z0-9_\.]+)\s*\(([^:]+):\s*(\d+)\)')
RE_AI_STATUS = re.compile(r'AI<div class="m"><div>(true|false)', re.IGNORECASE)
RE_THREAD_NAME = re.compile(r'Thread Name<div class="m"><div>([^<]+)')
RE_AUTHOR = re.compile(r'Author<div class="m"><div>([^(]+)\(([^:]+):\s*(\d+)\)')
RE_SENT = re.compile(r'Sent<div class="m"><div>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+UTC)')
RE_BODY = re.compile(r'Body<div class="m"><div>(.*?)<div class="p">', re.DOTALL)
RE_DISAPPEARING = re.compile(r'Disappearing Message<div class="m"><div>(On|Off)')
RE_DISAPPEARING_DURATION = re.compile(r'Disappearing Duration<div class="m"><div>([^<]+)')
RE_LINKED_MEDIA = re.compile(r'Linked Media File:<div class="m"><div>([^<]+)')
RE_SHARE_URL = re.compile(r'Url<div class="m"><div>([^<]+)')
RE_SHARE_TEXT = re.compile(r'Text<div class="m"><div>([^<]+)')
RE_CALL_TYPE = re.compile(r'Type<div class="m"><div>([^<]+)')
RE_CALL_DURATION = re.compile(r'Duration<div class="m"><div>(\d+)')
RE_CALL_MISSED = re.compile(r'Missed<div class="m"><div>(true|false)', re.IGNORECASE)

# Regex para Subscription Events (entradas/saídas de grupo)
RE_SUBSCRIPTION_TYPE = re.compile(r'Subscription Event.*?Type<div class="m"><div>(subscribe|unsubscribe)', re.DOTALL)
RE_SUBSCRIPTION_USERS = re.compile(r'Subscription Event.*?Users<div class="m"><div>(.*?)(?:</div>)', re.DOTALL)

# Regex para Past Participants
RE_PAST_PARTICIPANTS = re.compile(
    r'Past Participants<div class="m"><div>(.*?)(?=<div class="t o">|<div class="p"></div><div class="t o">)',
    re.DOTALL
)

# Regex para Read Receipts
RE_READ_RECEIPTS = re.compile(r'Read Receipts<div class="m"><div>(Enabled|Disabled)')

# Regex para detecção de pagamentos
RE_PAYMENT = re.compile(r'payment request was auto-detected', re.IGNORECASE)

# Regex para limpeza de conteúdo
RE_HTML_TAGS = re.compile(r'<[^>]+>')
RE_PAGE_BREAK = re.compile(r'Meta Platforms Business Record Page \d+', re.IGNORECASE)
RE_MULTIPLE_SPACES = re.compile(r'\s+')
# Regex para remover quebras de página completas (incluindo tags órfãs antes/depois)
# Captura os groups de fechamento/abertura separadamente para balanceamento
RE_PAGE_BREAK_FULL = re.compile(
    r'((?:</div>)*)\s*<div\s+id="page_\d+"\s+class="pageBreak">[^<]*</div>\s*((?:<div[^>]*>)*)',
    re.IGNORECASE
)
# Regex auxiliar para contar divs de abertura individuais
RE_OPENING_DIV = re.compile(r'<div[^>]*>')

# ============================================================================
# REGEX v5.2 — Conteúdo Rico (Fase 6)
# ============================================================================

# Unicode bidi isolate marks (U+2068 FSI, U+2069 PDI) — limpeza em bodies
RE_BIDI_MARKS = re.compile(r'[\u2068\u2069\u202A-\u202E\u2066\u2067]')

# @mention em bodies — captura @nome (nome pode conter letras, números, _, . e emojis simples)
# Após limpeza das marcas bidi, mentions ficam como "@nome"
RE_MENTION = re.compile(r'@([A-Za-z0-9_][\w.~\-⛓️🙌🏾🙏🏾]*)', re.UNICODE)

# URL no body — detecta http(s) URLs comuns em mensagens de texto
RE_URL_IN_BODY = re.compile(
    r'https?://(?:[-\w.])+(?:\.[a-zA-Z]{2,})+(?:/[^\s<>"\']*)?',
    re.IGNORECASE
)

# Extrai ID da mídia Instagram de URLs de reel/post
RE_INSTAGRAM_REEL_ID = re.compile(r'instagram\.com/(?:reel|p|tv)/([A-Za-z0-9_-]+)', re.IGNORECASE)

# Detecta voice message em bodies (após tradução)
RE_VOICE_MESSAGE_BODY = re.compile(
    r'^(?:You\s+)?sent\s+a\s+voice\s+message\.?$|^(?:Voc[êe]\s+)?enviou\s+uma\s+mensagem\s+de\s+voz\.?$',
    re.IGNORECASE
)

# Detecta Share block com apenas Date Created: Unknown (vazio)
# Um Share vazio tem o pattern: Share <div class="m"><div><div class="t o"><div class="t i">Date Created<div class="m"><div>Unknown<div class="p"></div></div></div></div></div><div class="p"></div></div></div>
# Sem URL, sem Text
RE_SHARE_EMPTY = re.compile(
    r'Share<div class="m"><div><div class="t o"><div class="t i">Date Created<div class="m"><div>Unknown<div class="p"></div></div></div></div></div>\s*<div class="p"></div>\s*</div></div>',
    re.IGNORECASE
)

# ============================================================================
# TRADUÇÕES AUTOMÁTICAS
# ============================================================================

TRANSLATIONS = {
    # Mensagens de voz
    "sent a voice message.": "enviou uma mensagem de voz.",
    "You sent a voice message.": "Você enviou uma mensagem de voz.",
    # Curtidas/Reações
    "Liked a message": "Curtiu uma mensagem",
    "liked a message": "curtiu uma mensagem",
    # Reações
    "Reacted": "Reagiu",
    "to your message": "à sua mensagem",
    # Fotos
    "a photo": "uma foto",
    # Anexos
    "sent an attachment.": "enviou um anexo.",
    "You sent an attachment.": "Você enviou um anexo.",
    "sent": "enviou",
    # Outras
    "sent a photo.": "enviou uma foto.",
    "You sent a photo.": "Você enviou uma foto.",
    "sent a video.": "enviou um vídeo.",
    "You sent a video.": "Você enviou um vídeo.",
    "sent a sticker.": "enviou um sticker.",
    "You sent a sticker.": "Você enviou um sticker.",
    "started a video chat.": "iniciou uma chamada de vídeo.",
    "started a call.": "iniciou uma chamada.",
    "You started a video chat": "Você iniciou uma chamada de vídeo",
    "started a video chat": "iniciou uma chamada de vídeo",
    "Video chat ended": "Chamada de vídeo encerrada",
    "You started an audio call": "Você iniciou uma chamada de áudio",
    "started an audio call": "iniciou uma chamada de áudio",
    "Audio call ended": "Chamada de áudio encerrada",
    # Chamadas perdidas
    "You missed an audio call": "Você perdeu uma chamada de áudio",
    "You missed a video call": "Você perdeu uma chamada de vídeo",
    "You missed a call": "Você perdeu uma chamada",
    "missed an audio call": "perdeu uma chamada de áudio",
    "missed a video call": "perdeu uma chamada de vídeo",
    "missed a call": "perdeu uma chamada",
    "Missed call": "Chamada perdida",
    "Missed audio call": "Chamada de áudio perdida",
    "Missed video call": "Chamada de vídeo perdida",
    # Chamadas - variações
    "The call ended": "A chamada terminou",
    "Call ended": "Chamada encerrada",
    "The video chat ended": "A chamada de vídeo terminou",
    "The audio call ended": "A chamada de áudio terminou",
    # Mensagens removidas
    "This message was deleted": "Esta mensagem foi apagada",
    "Message deleted": "Mensagem apagada",
    "removed a message": "removeu uma mensagem",
    # Grupos / Subscription Events
    "created the group": "criou o grupo",
    "added": "adicionou",
    "removed": "removeu",
    "left the group": "saiu do grupo",
    "joined the group": "entrou no grupo",
    "changed the group name": "alterou o nome do grupo",
    "changed the group photo": "alterou a foto do grupo",
    "named the group": "nomeou o grupo",
    # Pagamentos
    "A payment request was auto-detected.": "Uma solicitação de pagamento foi detectada automaticamente.",
    "payment request was auto-detected": "solicitação de pagamento foi detectada",
    # Respostas
    "Replied to": "Respondeu a",
    "replied to": "respondeu a",
    # Encaminhamentos
    "Forwarded": "Encaminhado",
    "forwarded a message": "encaminhou uma mensagem",
    # GIFs
    "sent a GIF": "enviou um GIF",
    "You sent a GIF": "Você enviou um GIF",
    # Áudios
    "sent an audio": "enviou um áudio",
    "You sent an audio": "Você enviou um áudio",
    # Links
    "shared a link": "compartilhou um link",
    "You shared a link": "Você compartilhou um link",
    # Localização
    "shared a location": "compartilhou uma localização",
    "You shared a location": "Você compartilhou uma localização",
    "shared live location": "compartilhou localização em tempo real",
    # Contato
    "shared a contact": "compartilhou um contato",
    "You shared a contact": "Você compartilhou um contato",
    # Screenshots
    "You took a screenshot.": "Você tirou uma captura de tela.",
    "took a screenshot.": "tirou uma captura de tela.",
    "took a screenshot": "tirou uma captura de tela",
    "Screenshot taken": "Captura de tela feita",
}

# Chaves ordenadas por comprimento decrescente para tradução parcial segura
TRANSLATIONS_KEYS_SORTED = sorted(TRANSLATIONS.keys(), key=len, reverse=True)
