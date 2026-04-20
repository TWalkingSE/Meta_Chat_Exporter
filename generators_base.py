"""
Meta Platforms Chat Exporter - Base HTML Generator
Classe base com métodos compartilhados entre os geradores de HTML
"""

import hashlib
import html
import logging
import re
from pathlib import Path

from constants import (
    MONTHS, RE_MENTION, RE_URL_IN_BODY, RE_INSTAGRAM_REEL_ID,
    RE_VOICE_MESSAGE_BODY, RE_BIDI_MARKS
)
from models import Attachment, Message
from utils import translate_message


def _enrich_body_html(escaped_body: str) -> str:
    """Aplica enriquecimento visual no body já escapado em HTML:
    - Linkifica URLs (http/https)
    - Destaca @mentions com span.mention
    - Ícones especiais para wa.me (WhatsApp) e mpago.la (Mercado Pago)
    Entrada DEVE estar HTML-escaped (para segurança)."""
    if not escaped_body:
        return escaped_body

    # 1) Auto-linkify URLs. Como o body já está escaped, http(s):// ainda é detectável.
    def _url_repl(m):
        url = m.group(0)
        # Detectar tipo para ícone
        if 'wa.me/' in url or 'whatsapp.com/' in url.lower():
            icon = '💬 '
            cls = 'link-whatsapp'
        elif 'mpago.la' in url or 'mercadopago.com' in url.lower():
            icon = '💰 '
            cls = 'link-payment'
        elif 'instagram.com/' in url.lower():
            icon = '📷 '
            cls = 'link-instagram'
        else:
            icon = ''
            cls = 'link-external'
        # Encurtar texto visível (max 60 chars)
        display = url if len(url) <= 60 else url[:57] + '...'
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="body-link {cls}">{icon}{display}</a>'

    result = RE_URL_IN_BODY.sub(_url_repl, escaped_body)

    # 2) @mentions — só aplicar em partes que NÃO estão dentro de tags <a>
    #    Usamos split por tags e só processamos os segmentos de texto
    parts = re.split(r'(<a [^>]*>.*?</a>)', result, flags=re.DOTALL)
    out_parts = []
    for p in parts:
        if p.startswith('<a '):
            out_parts.append(p)
        else:
            p = RE_MENTION.sub(
                lambda m: f'<span class="mention">@{m.group(1)}</span>',
                p
            )
            out_parts.append(p)
    return ''.join(out_parts)

# Regex to detect emoji-only messages (up to 5 emojis, optional spaces)
_RE_EMOJI_ONLY = re.compile(
    r'^[\s]*(?:['
    r'\U0001F600-\U0001F64F'
    r'\U0001F300-\U0001F5FF'
    r'\U0001F680-\U0001F6FF'
    r'\U0001F1E0-\U0001F1FF'
    r'\U00002702-\U000027B0'
    r'\U0001F900-\U0001F9FF'
    r'\U0001FA00-\U0001FA6F'
    r'\U0001FA70-\U0001FAFF'
    r'\U00002600-\U000026FF'
    r'\U0000FE00-\U0000FE0F'
    r'\U0000200D'
    r'\U00002B50-\U00002B55'
    r'\U00002764'
    r']\s*){1,5}[\s]*$', re.UNICODE
)

logger = logging.getLogger(__name__)


class BaseHTMLGenerator:
    """Classe base com métodos compartilhados para geração de HTML"""

    MONTHS = MONTHS

    def __init__(self, owner_username: str, owner_id: str, transcriptions: dict = None):
        self.owner_username = owner_username
        self.owner_id = owner_id
        self.transcriptions = transcriptions or {}

    def _stream_template(self, template: str, replacements):
        """Itera um template, substituindo tokens por chunks sob demanda."""
        cursor = 0
        for token, producer in replacements:
            index = template.find(token, cursor)
            if index == -1:
                raise ValueError(f"Token de template não encontrado: {token}")
            if index > cursor:
                yield template[cursor:index]

            chunks = producer()
            if isinstance(chunks, str):
                if chunks:
                    yield chunks
            else:
                for chunk in chunks:
                    if chunk:
                        yield chunk

            cursor = index + len(token)

        if cursor < len(template):
            yield template[cursor:]

    def _write_chunks(self, output_path, chunks):
        """Escreve chunks sequencialmente em disco para evitar pico de memória."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as file_obj:
            for chunk in chunks:
                if chunk:
                    file_obj.write(chunk)
        return output_path

    def _get_transcription(self, filename: str) -> str:
        """Busca transcrição para um arquivo de áudio"""
        if not self.transcriptions or not filename:
            return ""

        # Tentar encontrar pelo nome exato (lowercase)
        filename_lower = filename.lower()
        if filename_lower in self.transcriptions:
            return self.transcriptions[filename_lower]

        # Tentar sem extensão
        name_no_ext = filename_lower.rsplit('.', 1)[0] if '.' in filename_lower else filename_lower
        if name_no_ext in self.transcriptions:
            return self.transcriptions[name_no_ext]

        # Tentar apenas o nome do arquivo (sem caminho)
        basename = filename_lower.split('/')[-1].split('\\')[-1]
        if basename in self.transcriptions:
            return self.transcriptions[basename]

        basename_no_ext = basename.rsplit('.', 1)[0] if '.' in basename else basename
        if basename_no_ext in self.transcriptions:
            return self.transcriptions[basename_no_ext]

        return ""

    def _get_transcription_html(self, filename: str) -> str:
        """Retorna HTML formatado para transcrição de áudio"""
        transcription = self._get_transcription(filename)
        if not transcription:
            return ""

        escaped_text = html.escape(transcription)
        return f'''<div class="audio-transcription">
            <span class="transcription-label">Transcrição:</span>
            <span class="transcription-text"><em>{escaped_text}</em></span>
        </div>'''

    def _is_owner(self, participant: tuple) -> bool:
        """Verifica se o participante é o dono da conta"""
        username, platform, user_id = participant
        return (user_id == self.owner_id or
                username.lower() == self.owner_username.lower())

    def _generate_attachment(self, att: Attachment) -> str:
        """Gera HTML para attachment"""
        # Rejeitar paths com traversal (../)
        if '..' in att.local_path:
            logger.warning("Path traversal detectado, ignorando anexo: %s", att.local_path)
            return ""
        path = html.escape(att.local_path.replace("\\", "/"))
        filename = html.escape(att.filename) if att.filename else ""
        # Gerar ID único baseado no caminho
        audio_id = hashlib.md5(att.local_path.encode('utf-8')).hexdigest()[:12]

        if "audio" in att.file_type:
            # Buscar transcrição se disponível
            transcription_html = self._get_transcription_html(att.filename)

            # Usar preload="none" para evitar carregamento simultâneo de múltiplos áudios
            return f'''<div class="attachment">
                <div class="audio-container">
                    <audio id="audio-{audio_id}" controls preload="none">
                        <source src="{path}" type="audio/mp4">
                        <source src="{path}" type="audio/mpeg">
                        Seu navegador não suporta áudio.
                    </audio>
                    <div class="audio-speed">
                            <button class="active" onclick="setSpeed({audio_id}, 1, this)">1x</button>
                            <button onclick="setSpeed({audio_id}, 1.5, this)">1.5x</button>
                            <button onclick="setSpeed({audio_id}, 2, this)">2x</button>
                    </div>
                </div>
                {transcription_html}
                <div class="attachment-filename">{filename}</div>
            </div>'''
        elif "video" in att.file_type:
            return f'''<div class="attachment">
                <video controls preload="none" loading="lazy" data-src="{path}#t=0.5" class="lazy-video"></video>
                <div class="attachment-filename">{filename}</div>
            </div>'''
        elif "image" in att.file_type:
            return f'''<div class="attachment">
                <img src="{path}" alt="Imagem" loading="lazy" onclick="openLightbox(this.src)">
                <div class="attachment-filename">{filename}</div>
            </div>'''
        else:
            return f'<div class="attachment"><div class="attachment-file"><span>📎</span><a href="{path}">{filename}</a></div></div>'

    def _generate_message_content(self, msg: Message) -> str:
        """Gera o conteúdo interno de uma mensagem (compartilhado entre geradores)"""
        content = ""
        if msg.removed_by_sender:
            content = '<span class="removed-message">🚫 Mensagem removida</span>'
        elif msg.is_call:
            icon = "📵" if msg.call_missed else "📞"
            duration = f" • {msg.call_duration//60}:{msg.call_duration%60:02d}" if msg.call_duration > 0 else ""
            missed = " • Perdida" if msg.call_missed else ""
            content = f'<div class="call-info {"missed" if msg.call_missed else ""}"><span>{icon}</span><span>Chamada{duration}{missed}</span></div>'
        elif msg.body:
            # Detectar mensagens de video chat e audio call
            body_lower = msg.body.lower()
            # Verificar chamadas perdidas primeiro
            if 'missed' in body_lower and 'video' in body_lower:
                content = '<div class="call-info video-call missed"><span>📵</span><span>Chamada de vídeo perdida</span></div>'
            elif 'missed' in body_lower and ('audio' in body_lower or 'call' in body_lower):
                content = '<div class="call-info audio-call missed"><span>📵</span><span>Chamada de áudio perdida</span></div>'
            elif 'started a video chat' in body_lower or 'video chat' in body_lower:
                if 'ended' in body_lower:
                    content = '<div class="call-info video-call ended"><span>⏹️</span><span>Chamada de vídeo encerrada</span></div>'
                else:
                    content = '<div class="call-info video-call"><span>▶️</span><span>Chamada de vídeo iniciada</span></div>'
            elif 'started an audio call' in body_lower or 'audio call' in body_lower:
                if 'ended' in body_lower:
                    content = '<div class="call-info audio-call ended"><span>📵</span><span>Chamada de áudio encerrada</span></div>'
                else:
                    content = '<div class="call-info audio-call"><span>📞</span><span>Chamada de áudio iniciada</span></div>'
            else:
                translated_body = translate_message(msg.body)
                # Phase 6.4: Voice message placeholder → ícone + pseudo-waveform
                if RE_VOICE_MESSAGE_BODY.match(translated_body.strip()):
                    content = (
                        '<div class="voice-msg-placeholder">'
                        '<span class="voice-msg-icon">🎤</span>'
                        '<div class="voice-msg-waveform" aria-hidden="true">'
                        + ''.join(f'<span style="height:{h}%"></span>' for h in (30, 60, 45, 80, 55, 70, 40, 90, 50, 65, 35, 75, 45, 60, 30)) +
                        '</div>'
                        '<span class="voice-msg-label">Mensagem de voz</span>'
                        '</div>'
                    )
                else:
                    emoji_class = " emoji-only" if _RE_EMOJI_ONLY.match(msg.body) else ""
                    escaped = html.escape(translated_body)
                    enriched = _enrich_body_html(escaped)
                    content = f'<div class="message-content{emoji_class}">{enriched}</div>'

        for att in msg.attachments:
            content += self._generate_attachment(att)

        if msg.share_url:
            content += self._generate_share_card(msg.share_url, msg.share_text)

        return content

    def _generate_share_card(self, share_url: str, share_text: str = None) -> str:
        """Gera card rico para shares do Instagram e outros serviços.
        Phase 6.1 — v5.2."""
        url = share_url.strip()
        text = (share_text or "").strip()
        # Detectar tipo de share
        lower = url.lower()
        reel_match = RE_INSTAGRAM_REEL_ID.search(url)

        if reel_match:
            reel_id = reel_match.group(1)
            kind = 'reel' if '/reel/' in lower else ('post' if '/p/' in lower else 'tv')
            icon_map = {'reel': '🎬', 'post': '📷', 'tv': '📺'}
            label_map = {'reel': 'Reel do Instagram', 'post': 'Post do Instagram', 'tv': 'IGTV'}
            icon = icon_map[kind]
            label = label_map[kind]
            caption_html = f'<div class="share-card-caption">{html.escape(text)}</div>' if text else ''
            return (
                f'<div class="share-card share-card-instagram">'
                f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" class="share-card-link">'
                f'<div class="share-card-header">'
                f'<span class="share-card-icon">{icon}</span>'
                f'<div class="share-card-meta">'
                f'<div class="share-card-title">{label}</div>'
                f'<div class="share-card-id">{html.escape(reel_id)}</div>'
                f'</div>'
                f'</div>'
                f'{caption_html}'
                f'<div class="share-card-url">{html.escape(url)}</div>'
                f'</a>'
                f'</div>'
            )

        # Fallback genérico: usar estilo existente
        text_safe = html.escape(text or "Link")
        url_safe = html.escape(url)
        return (
            f'<div class="share-link">'
            f'<a href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 {text_safe}</a>'
            f'<div class="share-url">{url_safe}</div>'
            f'</div>'
        )

    def _generate_disappearing_html(self, msg: Message) -> str:
        """Gera badge HTML para mensagens que desaparecem"""
        if not msg.disappearing:
            return ""
        if msg.disappearing_duration and 'immediately' in msg.disappearing_duration.lower():
            return '<span class="disappearing-badge view-once" title="Mensagem configurada para desaparecer (imediatamente após ser visto)">⏱️</span>'
        duration_text = msg.disappearing_duration or "tempo padrão"
        return f'<span class="disappearing-badge" title="Mensagem configurada para desaparecer ({duration_text})">⏱️</span>'

    def _format_time(self, msg: Message) -> str:
        """Formata timestamp da mensagem"""
        return msg.sent.strftime("%d/%m/%Y às %H:%M:%S") if msg.sent else ""
