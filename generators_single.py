"""
Meta Platforms Chat Exporter - Gerador HTML de Chat Individual
Gera HTML para visualização de uma única conversa
"""

import html
import logging
from datetime import datetime
from pathlib import Path

from generators_base import BaseHTMLGenerator
from models import Message, Thread

logger = logging.getLogger(__name__)


class ChatHTMLGenerator(BaseHTMLGenerator):
    """Gera HTML bonito para visualização de um chat individual"""

    _MESSAGES_TOKEN = "__META_CHAT_MESSAGES__"

    def __init__(self, thread: Thread, owner_username: str, owner_id: str, transcriptions: dict = None):
        super().__init__(owner_username, owner_id, transcriptions)
        self.thread = thread

    def generate(self) -> str:
        """Gera o HTML completo do chat"""
        return "".join(self.iter_generate())

    def write_to_file(self, output_path: Path) -> Path:
        """Escreve o HTML diretamente em disco para reduzir uso de memória."""
        return self._write_chunks(output_path, self.iter_generate())

    def iter_generate(self):
        """Itera o HTML do chat em chunks."""
        chat_name, period, participants_html = self._build_render_context()
        template = self._get_template(chat_name, period, participants_html, self._MESSAGES_TOKEN)
        yield from self._stream_template(
            template,
            [(self._MESSAGES_TOKEN, self._iter_messages_html)],
        )

    def _build_render_context(self):
        """Prepara contexto de renderização do chat."""
        # Filtrar apenas interlocutores (excluir owner)
        others = [p for p in self.thread.participants if not self._is_owner(p)]

        if self.thread.thread_name:
            chat_name = self.thread.thread_name
        else:
            chat_name = ", ".join([p[0] for p in others]) if others else f"Conversa {self.thread.thread_id}"

        period = ""
        if self.thread.messages:
            first = self.thread.messages[0].sent
            last = self.thread.messages[-1].sent
            if first and last:
                period = f"{first.strftime('%d/%m/%Y')} - {last.strftime('%d/%m/%Y')}"

        # Mostrar apenas interlocutores na lista de participantes
        participants_html = "".join([
            f'<span class="participant">{p[0]} <small>({p[1]})</small></span>'
            for p in others
        ])

        return chat_name, period, participants_html

    def _generate_messages(self) -> str:
        """Gera HTML das mensagens."""
        return "".join(self._iter_messages_html())

    def _iter_messages_html(self):
        """Itera HTML das mensagens em pequenos chunks."""
        last_date = None
        first_message = True

        for msg in self.thread.messages:
            # Separador de data - sempre mostrar na primeira mensagem
            if msg.sent:
                msg_date = msg.sent.date()
                if msg_date != last_date or first_message:
                    date_str = f"{msg_date.day} de {self.MONTHS[msg_date.month-1]} de {msg_date.year}"
                    yield f'<div class="date-separator"><span>{date_str}</span></div>'
                    last_date = msg_date
                    first_message = False
            elif first_message:
                yield '<div class="date-separator"><span>Início da conversa</span></div>'
                first_message = False

            is_sent = (msg.author == self.owner_username or
                       msg.author_id == self.owner_id or
                       (msg.body and msg.body.startswith("You ")))

            yield self._generate_message(msg, is_sent)

    def _generate_message(self, msg: Message, is_sent: bool) -> str:
        """Gera HTML de uma mensagem"""
        msg_class = "sent" if is_sent else "received"

        content = self._generate_message_content(msg)
        time_str = self._format_time(msg)
        disappearing = self._generate_disappearing_html(msg)
        author_html = f'<div class="message-author">{html.escape(msg.author)}</div>' if not is_sent else ""

        return f'''<div class="message {msg_class}">
            <div class="message-bubble">
                {author_html}
                {content}
                <div class="message-time">{time_str}{disappearing}</div>
            </div>
        </div>'''

    def _get_template(self, chat_name: str, period: str, participants: str, messages: str) -> str:
        """Retorna template HTML completo"""
        return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(chat_name)} - Chat</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:linear-gradient(180deg,#c8c8c8 0%,#d9d9d9 50%,#e5e5e5 100%);min-height:100vh;color:#333}}
        .container{{max-width:900px;margin:0 auto;padding:20px}}
        .chat-header{{background:#fff;backdrop-filter:blur(10px);border-radius:20px;padding:30px;margin-bottom:20px;border:1px solid #e0e0e0;box-shadow:0 2px 10px rgba(0,0,0,0.05)}}
        .chat-header h1{{font-size:28px;font-weight:700;margin-bottom:10px;color:#333}}
        .chat-meta{{display:flex;flex-wrap:wrap;gap:15px;margin-top:15px;font-size:14px;color:#666}}
        .chat-meta span{{display:flex;align-items:center;gap:5px}}
        .participants{{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}}
        .participant{{background:#f0f0f0;padding:5px 12px;border-radius:20px;font-size:13px;border:1px solid #ddd}}
        .participant small{{color:#888}}
        .messages{{display:flex;flex-direction:column;gap:10px}}
        .date-separator{{text-align:center;padding:20px 0}}
        .date-separator span{{background:#555;padding:8px 20px;border-radius:20px;font-size:12px;color:#fff;font-weight:500}}
        .message{{display:flex;flex-direction:column;max-width:80%}}
        .message.sent{{align-self:flex-end}}
        .message.received{{align-self:flex-start}}
        .message-bubble{{padding:12px 16px;border-radius:18px;box-shadow:0 1px 3px rgba(0,0,0,0.12)}}
        .message.sent .message-bubble{{background:linear-gradient(135deg,#505050,#6b6b6b);color:#fff;border-bottom-right-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,0.2)}}
        .message.received .message-bubble{{background:#fff;border:1px solid #ddd;color:#333;border-bottom-left-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}}
        .message-author{{font-size:12px;font-weight:600;color:#555;margin-bottom:4px}}
        .message.sent .message-author{{display:none}}
        .message-content{{font-size:15px;line-height:1.5;word-wrap:break-word}}
        .message.sent .message-content{{color:#fff}}
        .message.received .message-content{{color:#333}}
        .message-time{{font-size:11px;color:#666;margin-top:5px;text-align:right}}
        .message.sent .message-time{{color:rgba(255,255,255,0.7)}}
        .attachment{{margin-top:10px;border-radius:12px;overflow:hidden}}
        .audio-container{{display:flex;flex-direction:column;gap:6px;padding:8px;background:#f0f0f0;border-radius:10px;min-width:280px}}
        .message.sent .audio-container{{background:rgba(255,255,255,0.2)}}
        .audio-container audio{{width:100%;height:36px}}
        .audio-transcription{{margin-top:8px;padding:10px 12px;background:#e8e8e8;border-radius:8px;font-size:13px;line-height:1.5}}
        .message.sent .audio-transcription{{background:rgba(255,255,255,0.15)}}
        .transcription-label{{font-weight:600;color:#555;display:block;margin-bottom:4px;font-size:11px}}
        .message.sent .transcription-label{{color:rgba(255,255,255,0.8)}}
        .transcription-text{{color:#333}}
        .message.sent .transcription-text{{color:rgba(255,255,255,0.9)}}
        .audio-speed{{display:flex;gap:5px;justify-content:center}}
        .audio-speed button{{padding:4px 10px;border:none;border-radius:12px;background:#ddd;color:#555;font-size:11px;cursor:pointer;transition:all .2s}}
        .audio-speed button:hover{{background:#ccc;color:#333}}
        .audio-speed button.active{{background:linear-gradient(135deg,#555,#777);color:#fff}}
        .attachment audio{{width:100%;height:40px}}
        .attachment video,.attachment img{{max-width:100%;max-height:300px;border-radius:12px;cursor:pointer}}
        .attachment-file{{display:flex;align-items:center;gap:10px;padding:10px 15px;background:#f0f0f0;border-radius:10px}}
        .message.sent .attachment-file{{background:rgba(255,255,255,0.2)}}
        .attachment-file a{{color:#555;text-decoration:none}}
        .message.sent .attachment-file a{{color:#fff}}
        .attachment-filename{{font-size:10px;color:#999;margin-top:6px;padding:4px 8px;word-break:break-word;text-align:center;line-height:1.3;background:rgba(0,0,0,0.03);border-radius:4px}}
        .message.sent .attachment-filename{{color:rgba(255,255,255,0.7);background:rgba(255,255,255,0.1)}}
        .call-info{{display:flex;align-items:center;gap:10px;padding:10px 15px;background:#f0f0f0;border-radius:10px}}
        .message.sent .call-info{{background:rgba(255,255,255,0.2)}}
        .call-info.missed{{border-left:3px solid #e74c3c}}
        .call-info.video-call{{border-left:3px solid #9b59b6}}
        .call-info.video-call.ended{{border-left:3px solid #95a5a6}}
        .call-info.audio-call{{border-left:3px solid #3498db}}
        .call-info.audio-call.ended{{border-left:3px solid #95a5a6}}
        .share-link{{margin-top:8px;padding:10px 15px;background:#f0f0f0;border-radius:10px}}
        .message.sent .share-link{{background:rgba(255,255,255,0.2)}}
        .share-link a{{color:#555;text-decoration:none;font-size:13px;word-break:break-all}}
        .message.sent .share-link a{{color:#fff}}
        .share-link a:hover{{text-decoration:underline}}
        .share-url{{font-size:10px;color:#888;margin-top:6px;word-break:break-all;line-height:1.3;padding:4px 6px;background:rgba(0,0,0,0.05);border-radius:4px;font-family:monospace}}
        .message.sent .share-url{{color:rgba(255,255,255,0.6);background:rgba(255,255,255,0.1)}}
        .removed-message{{font-style:italic;color:#999}}
        .disappearing-badge{{margin-left:6px;font-size:14px;filter:grayscale(100%);opacity:0.7;cursor:help}}
        .disappearing-badge.view-once{{filter:sepia(1) saturate(5) hue-rotate(175deg);opacity:1}}
        .footer{{text-align:center;padding:40px 20px;color:#999;font-size:12px}}
        .lightbox{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.95);z-index:1000;justify-content:center;align-items:center;cursor:pointer}}
        .lightbox img{{max-width:95%;max-height:95%;object-fit:contain}}
        .lightbox.active{{display:flex}}
        @media(max-width:600px){{.message{{max-width:90%}}.chat-header h1{{font-size:22px}}}}
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-header">
            <h1>💬 {html.escape(chat_name)}</h1>
            <div class="chat-meta">
                <span>📅 {period}</span>
                <span>💬 {len(self.thread.messages)} mensagens</span>
            </div>
            <div class="participants">{participants}</div>
        </div>
        <div class="messages">{messages}</div>
        <div class="footer">
            <p>Meta Chat Exporter</p>
            <p>Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>
    </div>
    <div class="lightbox" onclick="this.classList.remove('active')"><img src="" alt=""></div>
    <script>
        function openLightbox(src){{const l=document.querySelector('.lightbox');l.querySelector('img').src=src;l.classList.add('active')}}
        function setSpeed(audioId, speed, btn){{
            const audio=document.getElementById('audio-'+audioId);
            if(audio){{audio.playbackRate=speed;}}
            const container=btn.parentElement;
            container.querySelectorAll('button').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
        }}

        // Lazy load de metadados de áudio (carrega duração quando visível)
        const audioObserver = new IntersectionObserver((entries) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    const audio = entry.target;
                    if (audio.preload === 'none') {{
                        audio.preload = 'metadata';
                    }}
                    audioObserver.unobserve(audio);
                }}
            }});
        }}, {{ rootMargin: '100px' }});
        document.querySelectorAll('audio').forEach(audio => audioObserver.observe(audio));

        // Pausar outros áudios/vídeos quando um novo é iniciado
        let currentlyPlaying = null;
        document.querySelectorAll('audio, video').forEach(media => {{
            media.addEventListener('play', function() {{
                if (currentlyPlaying && currentlyPlaying !== this) {{
                    currentlyPlaying.pause();
                }}
                currentlyPlaying = this;
            }});
            media.addEventListener('ended', function() {{
                if (currentlyPlaying === this) currentlyPlaying = null;
            }});
        }});
    </script>
</body>
</html>'''
