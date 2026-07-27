"""
Meta Platforms Chat Exporter - Gerador HTML de Todas as Conversas
Gera um único HTML com todas as conversas (sidebar + chat)
"""

import html
import logging
from datetime import datetime
from pathlib import Path

from meta_chat_exporter.generators_base import BaseHTMLGenerator
from meta_chat_exporter.models import Message, ProfileMedia, Thread
from meta_chat_exporter.stats import ChatStatistics
from meta_chat_exporter.templates_all import AllChatsTemplateMixin
from meta_chat_exporter.utils import translate_message

logger = logging.getLogger(__name__)


class AllChatsHTMLGenerator(AllChatsTemplateMixin, BaseHTMLGenerator):
    """Gera um único HTML com todas as conversas (sidebar + chat)"""

    _SIDEBAR_TOKEN = "__META_CHAT_SIDEBAR__"
    _CHATS_TOKEN = "__META_CHAT_CHATS__"
    _CHAT_MESSAGES_TOKEN = "__META_CHAT_MESSAGES__"
    _GLOBAL_MEDIA_TOKEN = "__META_CHAT_GLOBAL_MEDIA__"
    _STATS_TOKEN = "__META_CHAT_STATS__"
    _PROFILE_MEDIA_TOKEN = "__META_CHAT_PROFILE_MEDIA__"
    _GLOBAL_CATEGORIES_TOKEN = "__META_CHAT_GLOBAL_CATEGORIES__"

    def __init__(
        self,
        threads: list[Thread],
        owner_username: str,
        owner_id: str,
        transcriptions: dict | None = None,
        profile_media: ProfileMedia | None = None,
        base_dir=None,
        redact: bool = False,
        already_redacted: bool = False,
    ):
        super().__init__(owner_username, owner_id, transcriptions)
        self.threads = threads
        self.profile_media = profile_media or ProfileMedia()
        self.base_dir = base_dir
        # Phase 8.3 — Redaction mode
        self.redact = redact
        # `already_redacted` indica que a Data_Layer já foi redigida uma única
        # vez na origem (CLI/GUI via `RedactionEngine`), conforme R4.1. Nesse
        # caso, mantemos o selo "Redigido" (via `self.redact`) sem reaplicar a
        # redação aqui, evitando depender da idempotência duas vezes.
        if redact and not already_redacted:
            self._apply_redaction()

    def _apply_redaction(self):
        """Aplica a redação in-place nos threads para garantir que nenhum dado
        sensível vaze no HTML.

        A lógica foi centralizada em `RedactionEngine` (módulo `redaction.py`),
        que é o ponto único de redação da Data_Layer. Este método delega para o
        motor, preservando o comportamento observável do gerador."""
        from meta_chat_exporter.redaction import RedactionEngine

        RedactionEngine(self.owner_username).redact(self.threads, self.profile_media)

    def generate(self) -> str:
        """Gera o HTML completo com todas as conversas"""
        return "".join(self.iter_generate())

    def write_to_file(self, output_path: Path) -> Path:
        """Escreve o HTML diretamente em disco para reduzir o pico de memória."""
        return self._write_chunks(output_path, self.iter_generate())

    def _build_render_context(self) -> dict:
        """Prepara contexto de renderização sem montar blocos HTML pesados."""
        # Contar totais
        total_msgs = sum(len(t.messages) for t in self.threads)

        # Calcular datas mínima e máxima de todas as mensagens
        all_dates = []
        for t in self.threads:
            for m in t.messages:
                if m.sent:
                    all_dates.append(m.sent)

        min_date = min(all_dates).strftime("%Y-%m-%d") if all_dates else ""
        max_date = max(all_dates).strftime("%Y-%m-%d") if all_dates else ""

        # Preparar galeria global de mídias sem montar o HTML inteiro ainda
        logger.info("Preparando galeria global de mídias...")
        global_media_items, global_media_counts = self._collect_global_media_items()
        total_media = global_media_counts["total"]
        logger.info("Galeria global preparada! Total: %d mídias", total_media)

        # Gerar painel de estatísticas
        logger.info("Gerando estatísticas...")
        stats_gen = ChatStatistics(
            self.threads, self.owner_username, self.owner_id, base_dir=self.base_dir
        )
        stats_html = stats_gen.generate_html_report()
        stats_css = ChatStatistics.get_stats_css()
        stats_js = ChatStatistics.get_stats_js()
        logger.info("Estatísticas geradas!")

        # --- Categorias Genéricas (Painel Único Agrupado) ---
        global_categories_count = (
            len(self.profile_media.generic_categories)
            if self.profile_media and self.profile_media.generic_categories
            else 0
        )
        global_categories_buttons = ""
        if global_categories_count:
            global_categories_buttons = (
                f'<button class="btn-global-media" onclick="toggleGlobalCatPanel()" '
                f'aria-label="Abrir outras categorias de dados">'
                f"🗂️ Outras Categorias ({global_categories_count})</button>"
            )

        # Gerar painel de mídias do perfil (Photos, Videos, Stories)
        has_profile_media = self.profile_media.has_media
        profile_media_css = ""
        profile_media_js = ""
        if has_profile_media:
            profile_media_css = self._get_profile_media_css()
            profile_media_js = self._get_profile_media_js()

        return {
            "total_threads": len(self.threads),
            "total_msgs": total_msgs,
            "min_date": min_date,
            "max_date": max_date,
            "global_media_items": global_media_items,
            "global_media_counts": global_media_counts,
            "total_media": total_media,
            "stats_html": stats_html,
            "stats_css": stats_css,
            "stats_js": stats_js,
            "has_profile_media": has_profile_media,
            "profile_media_css": profile_media_css,
            "profile_media_js": profile_media_js,
            "has_global_categories": bool(global_categories_count),
            "global_categories_count": global_categories_count,
            "global_categories_buttons": global_categories_buttons,
        }

    def iter_generate(self):
        """Itera o HTML unificado em chunks para exportação incremental."""
        context = self._build_render_context()
        template = self._get_full_template_skeleton(context)

        def _sidebar_chunks():
            logger.info("Gerando sidebar...")
            yield self._generate_sidebar()
            logger.info("Sidebar gerada!")

        def _chat_chunks():
            logger.info("Gerando chats...")
            yield from self._iter_all_chats_html()
            logger.info("Chats gerados!")

        def _global_media_chunks():
            logger.info("Gerando galeria global de mídias...")
            yield from self._iter_global_media_gallery(
                context["global_media_items"],
                context["global_media_counts"],
            )
            logger.info("Galeria global gerada!")

        def _profile_media_chunks():
            if not context["has_profile_media"]:
                return
            logger.info("Gerando painel de mídias do perfil...")
            yield from self._iter_profile_media_panel()
            logger.info(
                "Painel de mídias do perfil gerado! Total: %d", self.profile_media.media_total
            )

        def _global_categories_chunks():
            if not context["has_global_categories"]:
                return
            logger.info("Gerando painel agrupado de Outras Categorias...")
            yield from self._iter_global_categories_panel()
            logger.info("Painel agrupado gerado!")

        yield from self._stream_template(
            template,
            [
                (self._SIDEBAR_TOKEN, _sidebar_chunks),
                (self._CHATS_TOKEN, _chat_chunks),
                (self._GLOBAL_MEDIA_TOKEN, _global_media_chunks),
                (self._STATS_TOKEN, lambda: context["stats_html"]),
                (self._PROFILE_MEDIA_TOKEN, _profile_media_chunks),
                (self._GLOBAL_CATEGORIES_TOKEN, _global_categories_chunks),
            ],
        )

    def _generate_sidebar(self) -> str:
        """Gera a sidebar com lista de conversas"""
        items = []
        for i, thread in enumerate(self.threads):
            others = [p for p in thread.participants if not self._is_owner(p)]
            if thread.thread_name:
                name = thread.thread_name
                username = ", ".join([f"@{p[0]}" for p in others[:2]])
                if len(others) > 2:
                    username += f" +{len(others)-2}"
            else:
                name = (
                    ", ".join([p[0] for p in others[:2]])
                    if others
                    else f"Thread {thread.thread_id[:8]}"
                )
                username = ", ".join([f"@{p[0]}" for p in others[:2]]) if others else ""
                if len(others) > 2:
                    name += f" +{len(others)-2}"
                    username += f" +{len(others)-2}"

            last_msg = ""
            last_time = ""
            date_start = ""
            date_end = ""
            if thread.messages:
                last = thread.messages[-1]
                if last.is_call:
                    if last.call_missed:
                        last_msg = "📵 Chamada perdida"
                    else:
                        duration = (
                            f" ({last.call_duration//60}:{last.call_duration%60:02d})"
                            if last.call_duration > 0
                            else ""
                        )
                        last_msg = f"📞 Chamada{duration}"
                elif last.body:
                    translated_preview = translate_message(last.body)
                    last_msg = (
                        translated_preview[:40] + "..."
                        if len(translated_preview) > 40
                        else translated_preview
                    )
                elif last.share_url:
                    last_msg = "🔗 Link compartilhado"
                elif last.attachments:
                    att_type = last.attachments[0].file_type if last.attachments else ""
                    if "audio" in att_type:
                        last_msg = "🎤 Mensagem de voz"
                    elif "video" in att_type:
                        last_msg = "🎬 Vídeo"
                    elif "image" in att_type:
                        last_msg = "📷 Foto"
                    else:
                        last_msg = "📎 Anexo"
                else:
                    last_msg = "📎 Mídia"

                for msg in thread.messages:
                    if msg.sent:
                        date_start = msg.sent.strftime("%Y-%m-%d")
                        break
                for msg in reversed(thread.messages):
                    if msg.sent:
                        date_end = msg.sent.strftime("%Y-%m-%d")
                        last_time = msg.sent.strftime("%d/%m/%Y")
                        break

            active_class = "active" if i == 0 else ""
            items.append(f"""
                <div class="contact-item {active_class}" onclick="showChat({i})" data-start="{date_start}" data-end="{date_end}">
                    <div class="contact-avatar">💬</div>
                    <div class="contact-info">
                        <div class="contact-name">{html.escape(name[:25])}</div>
                        <div class="contact-username">{html.escape(username[:30])}</div>
                        <div class="contact-preview">{html.escape(last_msg)}</div>
                    </div>
                    <div class="contact-meta">
                        <div class="contact-time">{last_time}</div>
                        <div class="contact-count" data-total="{len(thread.messages)}">{len(thread.messages)}</div>
                    </div>
                </div>
            """)

        return "\n".join(items)

    def _iter_all_chats_html(self):
        """Itera as áreas de chat sem concatenar tudo previamente."""
        total = len(self.threads)
        for i, thread in enumerate(self.threads):
            if i % 20 == 0:
                logger.debug("Gerando chat %d/%d...", i + 1, total)
            display = "flex" if i == 0 else "none"

            others = [p for p in thread.participants if not self._is_owner(p)]
            if thread.thread_name:
                chat_name = thread.thread_name
            else:
                chat_name = (
                    ", ".join([p[0] for p in others])
                    if others
                    else f"Thread {thread.thread_id[:8]}"
                )

            interlocutor_username = f"@{others[0][0]}" if others else ""

            # Contar mídias da conversa (sem duplicatas)
            seen_media_names = set()
            media_count = 0
            for msg in thread.messages:
                for att in msg.attachments:
                    if (
                        "image" in att.file_type
                        or "video" in att.file_type
                        or "audio" in att.file_type
                    ):
                        filename_key = att.filename.lower().strip()
                        if filename_key not in seen_media_names:
                            seen_media_names.add(filename_key)
                            media_count += 1

            media_gallery_html = self._generate_media_gallery(thread, i)

            # Phase 7.3: Compute first/last message dates for date picker
            msg_dates = [m.sent for m in thread.messages if m.sent]
            first_date_iso = min(msg_dates).strftime("%Y-%m-%d") if msg_dates else ""
            last_date_iso = max(msg_dates).strftime("%Y-%m-%d") if msg_dates else ""
            date_picker_html = ""
            if first_date_iso and last_date_iso:
                date_picker_html = (
                    f'<button class="btn-date-picker" onclick="toggleDatePicker({i})" title="Ir para data" aria-label="Ir para data">📅</button>'
                    f'<div class="date-picker-popover" id="date-picker-{i}">'
                    f"<label>Ir para:</label>"
                    f'<input type="date" min="{first_date_iso}" max="{last_date_iso}" value="{first_date_iso}" '
                    f'onchange="__jumpToDate({i}, this.value)">'
                    f"</div>"
                )

            chat_template = f"""
                <div class="chat-container" id="chat-{i}" style="display: {display};">
                    <div class="chat-header">
                        <div class="chat-header-info">
                            <div class="chat-header-avatar">💬</div>
                            <div>
                                <div class="chat-header-name">{html.escape(chat_name)}</div>
                                <div class="chat-header-participants">{html.escape(interlocutor_username)}</div>
                            </div>
                        </div>
                        <div class="chat-header-meta">
                            <span class="chat-msg-count" id="chat-msg-count-{i}" data-total="{len(thread.messages)}">📝 {len(thread.messages)} mensagens</span>
                            <div class="color-legend" aria-label="Legenda de cores das mensagens">
                                <span><i class="swatch swatch-sent" aria-hidden="true"></i> Alvo</span>
                                <span><i class="swatch swatch-received" aria-hidden="true"></i> Interlocutores</span>
                            </div>
                            <button class="btn-media-gallery" onclick="openMediaGallery({i})">Ver mídias dessa conversa ({media_count})</button>
                            {date_picker_html}
                            <button class="btn-chat-stats" onclick="toggleChatStats({i})" title="Estatísticas desta conversa" aria-label="Mini-stats">📊</button>
                            <button class="btn-chat-pdf" onclick="exportChatPDF({i})" title="Exportar como PDF" aria-label="Exportar PDF">📄 PDF</button>
                            <button class="btn-details-toggle" id="btn-details-{i}" onclick="toggleDetails({i})">ℹ️ Ver detalhes</button>
                            <div class="search-nav" id="search-nav-{i}" style="display: none;">
                                <button class="search-nav-btn" onclick="navSearchPrev({i})">◀</button>
                                <span class="search-nav-info" id="search-nav-info-{i}">0/0</span>
                                <button class="search-nav-btn" onclick="navSearchNext({i})">▶</button>
                            </div>
                        </div>
                    </div>
                    <div class="chat-mini-stats" id="chat-mini-stats-{i}" style="display:none;" data-chat="{i}"></div>
                    <div class="chat-messages">
                        {self._CHAT_MESSAGES_TOKEN}
                    </div>
                    {media_gallery_html}
                </div>
            """
            yield from self._stream_template(
                chat_template,
                [
                    (
                        self._CHAT_MESSAGES_TOKEN,
                        lambda thread=thread, index=i: self._iter_messages_html(thread, index),
                    )
                ],
            )

    def _generate_messages(self, thread: Thread, chat_index: int = 0) -> str:
        """Gera HTML das mensagens de um thread.
        Para conversas com mais de PAGE_SIZE mensagens, adiciona paginação
        progressiva para evitar travamento do navegador.
        """
        return "".join(self._iter_messages_html(thread, chat_index))

    def _iter_messages_html(self, thread: Thread, chat_index: int = 0):
        """Itera o HTML das mensagens do thread em chunks."""
        PAGE_SIZE = 500
        total_msgs = len(thread.messages)
        use_pagination = total_msgs > PAGE_SIZE

        last_date = None
        first_message = True
        prev_author = None
        prev_sent = None

        # Se usar paginação, adicionar botão "Carregar mais" no topo
        if use_pagination:
            hidden_count = total_msgs - PAGE_SIZE
            yield (
                f'<div class="load-more-container" id="load-more-{chat_index}">'
                f'<button class="btn-load-more" onclick="loadMoreMessages({chat_index})">'
                f"⬆️ Carregar {hidden_count} mensagens anteriores"
                f"</button></div>"
            )

        # Phase 6.5: Past Participants como system messages
        if thread.past_participants:
            import html as html_mod

            for pp in thread.past_participants:
                uname = html_mod.escape(pp.username if hasattr(pp, "username") else str(pp))
                yield (
                    f'<div class="system-message" data-date="">'
                    f"<span>👋 {uname} saiu da conversa</span>"
                    f"</div>"
                )

        for msg_index, msg in enumerate(thread.messages):
            date_changed = False
            if msg.sent:
                msg_date = msg.sent.date()
                if msg_date != last_date or first_message:
                    date_str = (
                        f"{msg_date.day} de {self.MONTHS[msg_date.month-1]} de {msg_date.year}"
                    )
                    date_iso = msg_date.strftime("%Y-%m-%d")
                    # Ocultar separadores de data antigos na paginação
                    hidden_attr = ""
                    if use_pagination and msg_index < (total_msgs - PAGE_SIZE):
                        hidden_attr = ' style="display:none" data-paginated="true"'
                    yield f'<div class="date-separator" data-date="{date_iso}"{hidden_attr}><span>{date_str}</span></div>'
                    last_date = msg_date
                    first_message = False
                    date_changed = True
            elif first_message:
                hidden_attr = ""
                if use_pagination:
                    hidden_attr = ' style="display:none" data-paginated="true"'
                yield f'<div class="date-separator" data-date=""{hidden_attr}><span>Início da conversa</span></div>'
                first_message = False
                date_changed = True

            is_sent = (
                msg.author == self.owner_username
                or msg.author_id == self.owner_id
                or (msg.body and msg.body.startswith("You "))
            )

            # Detect grouped messages (same author, within 5 min, no date change)
            is_grouped = False
            if (
                not date_changed
                and prev_author == msg.author
                and msg.sent
                and prev_sent
                and (msg.sent - prev_sent).total_seconds() <= 300
            ):
                is_grouped = True

            # Ocultar mensagens antigas na paginação
            msg_html = self._generate_message(msg, is_sent, msg_index, chat_index, is_grouped)
            if use_pagination and msg_index < (total_msgs - PAGE_SIZE):
                # Inserir atributo de paginação no div da mensagem
                msg_html = msg_html.replace(
                    'class="message ',
                    'data-paginated="true" style="display:none" class="message ',
                    1,
                )
            yield msg_html
            prev_author = msg.author
            prev_sent = msg.sent

    def _generate_message(
        self,
        msg: Message,
        is_sent: bool,
        msg_index: int = 0,
        chat_index: int = 0,
        is_grouped: bool = False,
    ) -> str:
        """Gera HTML de uma mensagem"""
        msg_class = "sent" if is_sent else "received"
        grouped_class = " grouped" if is_grouped else ""

        content = self._generate_message_content(msg)
        time_str = self._format_time(msg)
        disappearing = self._generate_disappearing_html(msg)
        author_html = self._generate_author_html(msg, is_sent)

        # Atributos específicos do modo todas-conversas
        data_date = msg.sent.strftime("%Y-%m-%d") if msg.sent else ""
        msg_id = f"msg-{chat_index}-{msg_index}"
        source_file = html.escape(msg.source_file) if msg.source_file else "Desconhecido"
        source_tooltip = f"Origem: {source_file}"
        details_icon = f'<span class="msg-details-icon" data-tooltip="{source_tooltip}">i</span>'
        disappearing_attr = 'data-disappearing="true"' if msg.disappearing else ""
        edited_badge = (
            ' <span class="edited-badge" title="Mensagem editada">✏️</span>' if msg.is_edited else ""
        )

        # Phase 7.2: Copy button (apenas se mensagem tem texto)
        copy_btn = ""
        if msg.body and not msg.removed_by_sender and not msg.is_call:
            copy_btn = '<button class="msg-copy-btn" title="Copiar texto" aria-label="Copiar mensagem">📋</button>'

        return f"""<div class="message {msg_class}{grouped_class}" id="{msg_id}" data-date="{data_date}" data-source="{source_file}" {disappearing_attr}>
            <div class="message-bubble">
                {details_icon}
                {copy_btn}
                {author_html}
                {content}
                <div class="message-time">{time_str}{edited_badge}{disappearing}</div>
            </div>
        </div>"""

    def _generate_media_gallery(self, thread: Thread, chat_index: int) -> str:
        """Gera o painel de galeria de mídias para um thread"""
        media_items: list[dict] = []
        seen_paths: set[str] = set()
        count_images = 0
        count_videos = 0
        count_audios = 0

        for msg_index, msg in enumerate(thread.messages):
            for att in msg.attachments:
                filename_key = att.filename.lower().strip()
                if filename_key in seen_paths:
                    continue
                seen_paths.add(filename_key)

                media_type = ""
                if "image" in att.file_type:
                    media_type = "image"
                    count_images += 1
                elif "video" in att.file_type:
                    media_type = "video"
                    count_videos += 1
                elif "audio" in att.file_type:
                    media_type = "audio"
                    count_audios += 1
                else:
                    continue

                media_items.append(
                    {
                        "type": media_type,
                        "path": att.local_path.replace("\\", "/"),
                        "filename": att.filename,
                        "author": msg.author,
                        "sent": msg.sent,
                        "msg_id": f"msg-{chat_index}-{msg_index}",
                        "media_index": len(media_items),
                    }
                )

        total_media = count_images + count_videos + count_audios

        if total_media == 0:
            return f"""
                <div class="media-gallery-overlay" id="media-gallery-{chat_index}">
                    <div class="media-gallery-panel">
                    <div class="media-gallery-header">
                        <h3>Mídias da conversa</h3>
                        <button class="media-gallery-close" onclick="closeMediaGallery({chat_index})">✕</button>
                    </div>
                        <div class="media-gallery-content">
                            <div class="media-gallery-empty">
                                <div class="empty-icon"></div>
                                <div>Nenhuma mídia encontrada nesta conversa</div>
                            </div>
                        </div>
                    </div>
                </div>
            """

        items_html = []
        for item in media_items:
            path = html.escape(item["path"])
            date_str = (
                item["sent"].strftime("%d/%m/%Y às %H:%M:%S")
                if item["sent"]
                else "Data desconhecida"
            )
            author = html.escape(item["author"])
            msg_id = item["msg_id"]

            if item["type"] == "image":
                thumb_html = f'<img src="{path}" alt="Imagem" loading="lazy" onclick="openLightbox(this.src)">'
            elif item["type"] == "video":
                thumb_html = f'<video data-src="{path}#t=0.5" controls preload="none" class="lazy-video"></video>'
            else:
                audio_gallery_id = f"gallery-audio-{chat_index}-{item['media_index']}"
                transcription = self._get_transcription(item["filename"])
                transcription_gallery_html = ""
                if transcription:
                    transcription_escaped = html.escape(
                        transcription[:150] + "..." if len(transcription) > 150 else transcription
                    )
                    transcription_gallery_html = (
                        f'<div class="gallery-transcription"><em>{transcription_escaped}</em></div>'
                    )

                thumb_html = f"""
                    <div class="audio-icon">♪</div>
                    <div class="gallery-audio-container">
                        <audio id="{audio_gallery_id}" controls preload="none">
                            <source src="{path}" type="audio/mp4">
                            <source src="{path}" type="audio/mpeg">
                        </audio>
                        {self._generate_audio_speed_controls(audio_gallery_id)}
                        {transcription_gallery_html}
                    </div>
                """

            filename_display = html.escape(
                item["filename"][:30] + "..." if len(item["filename"]) > 30 else item["filename"]
            )
            items_html.append(f"""
                <div class="media-gallery-item type-{item['type']}" data-type="{item['type']}">
                    <div class="media-thumb">{thumb_html}</div>
                    <div class="media-gallery-item-info">
                        <div class="media-gallery-item-filename">{filename_display}</div>
                        <div class="media-gallery-item-date">{date_str}</div>
                        <div class="media-gallery-item-author">{author}</div>
                        <button class="media-go-to-msg" onclick="goToMediaMessage({chat_index}, '{msg_id}')">Ver na conversa</button>
                    </div>
                </div>
            """)

        items_joined = "\n".join(items_html)

        return f"""
            <div class="media-gallery-overlay" id="media-gallery-{chat_index}">
                <div class="media-gallery-panel">
                    <div class="media-gallery-header">
                        <h3>Mídias da conversa ({total_media})</h3>
                        <button class="media-gallery-close" onclick="closeMediaGallery({chat_index})">✕</button>
                    </div>
                    <div class="media-gallery-filters">
                        <button class="media-filter-btn active" onclick="filterMedia({chat_index}, 'all', this)">
                            Todas<span class="media-filter-count">{total_media}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterMedia({chat_index}, 'image', this)">
                            <span class="filter-icon-img"></span> Imagens<span class="media-filter-count">{count_images}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterMedia({chat_index}, 'video', this)">
                            🎬 Vídeos<span class="media-filter-count">{count_videos}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterMedia({chat_index}, 'audio', this)">
                            ♪ Áudios<span class="media-filter-count">{count_audios}</span>
                        </button>
                    </div>
                    <div class="media-gallery-content">
                        <div class="media-gallery-grid">
                            {items_joined}
                        </div>
                    </div>
                </div>
            </div>
        """

    def _collect_global_media_items(self) -> tuple[list[dict], dict[str, int]]:
        """Coleta metadados de mídias globais para renderização incremental."""
        media_items: list[dict] = []
        seen_paths: set[str] = set()
        count_images = 0
        count_videos = 0
        count_audios = 0

        for chat_index, thread in enumerate(self.threads):
            others = [p for p in thread.participants if not self._is_owner(p)]
            if thread.thread_name:
                chat_name = thread.thread_name
            else:
                chat_name = (
                    ", ".join([p[0] for p in others[:2]])
                    if others
                    else f"Thread {thread.thread_id[:8]}"
                )

            for msg_index, msg in enumerate(thread.messages):
                for att in msg.attachments:
                    filename_key = att.filename.lower().strip()
                    if filename_key in seen_paths:
                        continue
                    seen_paths.add(filename_key)

                    media_type = ""
                    if "image" in att.file_type:
                        media_type = "image"
                        count_images += 1
                    elif "video" in att.file_type:
                        media_type = "video"
                        count_videos += 1
                    elif "audio" in att.file_type:
                        media_type = "audio"
                        count_audios += 1
                    else:
                        continue

                    media_items.append(
                        {
                            "type": media_type,
                            "path": att.local_path.replace("\\", "/"),
                            "filename": att.filename,
                            "author": msg.author,
                            "sent": msg.sent,
                            "chat_index": chat_index,
                            "chat_name": chat_name,
                            "msg_id": f"msg-{chat_index}-{msg_index}",
                            "media_index": len(media_items),
                        }
                    )

        media_items.sort(key=lambda x: x["sent"] or datetime.min, reverse=True)
        return media_items, {
            "images": count_images,
            "videos": count_videos,
            "audios": count_audios,
            "total": count_images + count_videos + count_audios,
        }

    def _render_global_media_item(self, item: dict) -> str:
        """Renderiza um item da galeria global de mídias."""
        path = html.escape(item["path"])
        date_str = (
            item["sent"].strftime("%d/%m/%Y às %H:%M:%S") if item["sent"] else "Data desconhecida"
        )
        author = html.escape(item["author"])
        chat_name = html.escape(item["chat_name"][:25])
        chat_index = item["chat_index"]
        msg_id = item["msg_id"]

        if item["type"] == "image":
            thumb_html = (
                f'<img src="{path}" alt="Imagem" loading="lazy" onclick="openLightbox(this.src)">'
            )
        elif item["type"] == "video":
            thumb_html = f'<video data-src="{path}#t=0.5" controls preload="none" class="lazy-video"></video>'
        else:
            audio_gallery_id = f"global-audio-{item['media_index']}"
            transcription = self._get_transcription(item["filename"])
            transcription_gallery_html = ""
            if transcription:
                transcription_escaped = html.escape(
                    transcription[:150] + "..." if len(transcription) > 150 else transcription
                )
                transcription_gallery_html = (
                    f'<div class="gallery-transcription"><em>{transcription_escaped}</em></div>'
                )

            thumb_html = f"""
                    <div class="audio-icon">♪</div>
                    <div class="gallery-audio-container">
                        <audio id="{audio_gallery_id}" controls preload="none">
                            <source src="{path}" type="audio/mp4">
                            <source src="{path}" type="audio/mpeg">
                        </audio>
                        {self._generate_audio_speed_controls(audio_gallery_id)}
                        {transcription_gallery_html}
                    </div>
                """

        filename_display = html.escape(
            item["filename"][:30] + "..." if len(item["filename"]) > 30 else item["filename"]
        )
        return f"""
                <div class="media-gallery-item type-{item['type']}" data-type="{item['type']}">
                    <div class="media-thumb">{thumb_html}</div>
                    <div class="media-gallery-item-info">
                        <div class="media-gallery-item-chat">💬 {chat_name}</div>
                        <div class="media-gallery-item-filename">{filename_display}</div>
                        <div class="media-gallery-item-date">{date_str}</div>
                        <div class="media-gallery-item-author">{author}</div>
                        <button class="media-go-to-msg" onclick="goToGlobalMediaMessage({chat_index}, '{msg_id}')">Ver na conversa</button>
                    </div>
                </div>
            """

    def _iter_global_media_gallery(self, media_items=None, counts=None):
        """Itera o painel de galeria global de mídias sem montar um HTML monolítico."""
        if media_items is None or counts is None:
            media_items, counts = self._collect_global_media_items()

        total_media = counts["total"]
        if total_media == 0:
            yield """
                <div class="media-gallery-overlay" id="global-media-gallery">
                    <div class="media-gallery-panel">
                        <div class="media-gallery-header">
                            <h3>Todas as Mídias</h3>
                            <button class="media-gallery-close" onclick="closeGlobalMediaGallery()">✕</button>
                        </div>
                        <div class="media-gallery-content">
                            <div class="media-gallery-empty">
                                <div class="empty-icon">📭</div>
                                <div>Nenhuma mídia encontrada</div>
                            </div>
                        </div>
                    </div>
                </div>
            """
            return

        yield f"""
            <div class="media-gallery-overlay" id="global-media-gallery">
                <div class="media-gallery-panel global-panel">
                    <div class="media-gallery-header">
                        <h3>Todas as Mídias ({total_media})</h3>
                        <button class="media-gallery-close" onclick="closeGlobalMediaGallery()">✕</button>
                    </div>
                    <div class="media-gallery-filters">
                        <button class="media-filter-btn active" onclick="filterGlobalMedia('all', this)">
                            Todas<span class="media-filter-count">{total_media}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterGlobalMedia('image', this)">
                            <span class="filter-icon-img"></span> Imagens<span class="media-filter-count">{counts["images"]}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterGlobalMedia('video', this)">
                            🎬 Vídeos<span class="media-filter-count">{counts["videos"]}</span>
                        </button>
                        <button class="media-filter-btn" onclick="filterGlobalMedia('audio', this)">
                            ♪ Áudios<span class="media-filter-count">{counts["audios"]}</span>
                        </button>
                    </div>
                    <div class="media-gallery-content">
                        <div class="media-gallery-grid">
        """
        for item in media_items:
            yield self._render_global_media_item(item)
        yield """
                        </div>
                    </div>
                </div>
            </div>
        """

    def _iter_profile_photo_items(self):
        """Itera itens de fotos do perfil."""
        for photo in sorted(
            self.profile_media.photos, key=lambda item: item.taken or datetime.min, reverse=True
        ):
            date_str = (
                photo.taken.strftime("%d/%m/%Y %H:%M") if photo.taken else "Data desconhecida"
            )
            caption_html = (
                f'<div class="pm-caption">{html.escape(photo.caption)}</div>'
                if photo.caption
                else ""
            )
            location_html = (
                f'<div class="pm-location">📍 {html.escape(photo.location_name)}</div>'
                if photo.location_name
                else ""
            )
            likes_html = (
                f'<span class="pm-likes">❤️ {photo.like_count}</span>'
                if photo.like_count > 0
                else ""
            )
            category_html = (
                f'<div class="pm-category-badge" title="Categoria: {html.escape(photo.category)}">{html.escape(photo.category)}</div>'
                if photo.category
                else ""
            )
            source_html = (
                f'<div class="pm-source">📌 {html.escape(photo.source)}</div>'
                if photo.source
                else ""
            )
            filepath_display = html.escape(photo.local_path.replace("\\", "/"))
            yield f"""
                    <div class="pm-item" onclick="openProfileMediaLightbox(this)">
                        <img src="{html.escape(photo.local_path)}" loading="lazy" alt="Foto" />
                        {category_html}
                        <div class="pm-overlay">
                            <div class="pm-date">📅 {date_str}</div>
                            {caption_html}
                            {location_html}
                            {likes_html}
                            {source_html}
                            <div class="pm-privacy">{html.escape(photo.privacy)}</div>
                            <div class="pm-filepath" title="{filepath_display}">📁 {filepath_display}</div>
                        </div>
                    </div>"""

    def _iter_profile_video_items(self):
        """Itera itens de vídeos do perfil."""
        for video in sorted(
            self.profile_media.videos, key=lambda item: item.taken or datetime.min, reverse=True
        ):
            date_str = (
                video.taken.strftime("%d/%m/%Y %H:%M") if video.taken else "Data desconhecida"
            )
            caption_html = (
                f'<div class="pm-caption">{html.escape(video.caption)}</div>'
                if video.caption
                else ""
            )
            location_html = (
                f'<div class="pm-location">📍 {html.escape(video.location_name)}</div>'
                if video.location_name
                else ""
            )
            likes_html = (
                f'<span class="pm-likes">❤️ {video.like_count}</span>'
                if video.like_count > 0
                else ""
            )
            category_html = (
                f'<div class="pm-category-badge" title="Categoria: {html.escape(video.category)}">{html.escape(video.category)}</div>'
                if video.category
                else ""
            )
            source_html = (
                f'<div class="pm-source">📌 {html.escape(video.source)}</div>'
                if video.source
                else ""
            )
            escaped_path = html.escape(video.local_path)
            video_ext = (
                video.local_path.rsplit(".", 1)[-1].lower() if "." in video.local_path else "mp4"
            )
            video_mime = {
                "mp4": "video/mp4",
                "webm": "video/webm",
                "mov": "video/mp4",
                "avi": "video/x-msvideo",
                "mkv": "video/x-matroska",
            }.get(video_ext, "video/mp4")
            filepath_display = html.escape(video.local_path.replace("\\", "/"))
            yield f"""
                    <div class="pm-item pm-video-item">
                        <div class="pm-video-wrapper">
                            <video controls preload="metadata" playsinline>
                                <source src="{escaped_path}" type="{video_mime}" />
                                <source src="{escaped_path}" type="video/mp4" />
                                Seu navegador não suporta vídeo.
                            </video>
                        </div>
                        <div class="pm-video-badge">▶️</div>
                        {category_html}
                        <div class="pm-info-bar">
                            <div class="pm-date">📅 {date_str}</div>
                            {caption_html}
                            {location_html}
                            {likes_html}
                            {source_html}
                            <div class="pm-privacy">{html.escape(video.privacy)}</div>
                            <div class="pm-filepath" title="{filepath_display}">📁 {filepath_display}</div>
                        </div>
                    </div>"""

    def _iter_profile_story_items(self):
        """Itera itens de stories do perfil."""
        for story in sorted(
            self.profile_media.stories, key=lambda item: item.time or datetime.min, reverse=True
        ):
            date_str = story.time.strftime("%d/%m/%Y %H:%M") if story.time else "Data desconhecida"
            ai_badge = '<span class="pm-ai-badge">🤖 AI</span>' if story.ai_generated else ""
            category_html = (
                f'<div class="pm-category-badge" title="Categoria: {html.escape(story.category)}">{html.escape(story.category)}</div>'
                if story.category
                else ""
            )
            escaped_path = html.escape(story.local_path)
            story_filepath = html.escape(story.local_path.replace("\\", "/"))

            if story.media_type == "video":
                story_ext = (
                    story.local_path.rsplit(".", 1)[-1].lower()
                    if "." in story.local_path
                    else "mp4"
                )
                story_mime = {
                    "mp4": "video/mp4",
                    "webm": "video/webm",
                    "mov": "video/mp4",
                    "avi": "video/x-msvideo",
                    "mkv": "video/x-matroska",
                }.get(story_ext, "video/mp4")
                media_html = f"""
                        <div class="pm-video-wrapper">
                            <video controls preload="metadata" playsinline>
                                <source src="{escaped_path}" type="{story_mime}" />
                                <source src="{escaped_path}" type="video/mp4" />
                                Seu navegador não suporta vídeo.
                            </video>
                        </div>
                        <div class="pm-video-badge">▶️</div>"""
                yield f"""
                    <div class="pm-item pm-story-item pm-video-item">
                        {media_html}
                        {category_html}
                        <div class="pm-info-bar">
                            <div class="pm-date">📅 {date_str}</div>
                            {ai_badge}
                            <div class="pm-privacy">{html.escape(story.privacy)}</div>
                            <div class="pm-filepath" title="{story_filepath}">📁 {story_filepath}</div>
                        </div>
                    </div>"""
                continue

            media_html = f'<img src="{escaped_path}" loading="lazy" alt="Story" onclick="openProfileMediaLightbox(this)" />'
            yield f"""
                    <div class="pm-item pm-story-item">
                        {media_html}
                        {category_html}
                        <div class="pm-overlay">
                            <div class="pm-date">📅 {date_str}</div>
                            {ai_badge}
                            <div class="pm-privacy">{html.escape(story.privacy)}</div>
                            <div class="pm-filepath" title="{story_filepath}">📁 {story_filepath}</div>
                        </div>
                    </div>"""

    def _iter_profile_media_panel(self):
        """Itera o painel de mídias do perfil sem montar uma string única grande."""
        pm = self.profile_media
        if not pm.has_media:
            return

        img_count = len(pm.photos)
        vid_count = len(pm.videos)
        story_count = len(pm.stories)
        story_img = sum(1 for story in pm.stories if story.media_type == "image")
        story_vid = sum(1 for story in pm.stories if story.media_type == "video")

        sections = []
        if pm.photos:
            sections.append(
                ("pm-photos", f"📷 Fotos ({img_count})", self._iter_profile_photo_items, "pm-grid")
            )
        if pm.videos:
            sections.append(
                ("pm-videos", f"🎬 Vídeos ({vid_count})", self._iter_profile_video_items, "pm-grid")
            )
        if pm.stories:
            sections.append(
                (
                    "pm-stories",
                    f"📱 Stories ({story_count})",
                    self._iter_profile_story_items,
                    "pm-grid pm-grid-stories",
                )
            )

        tabs_html = []
        for index, (section_id, label, _producer, _grid_class) in enumerate(sections):
            active_class = " active" if index == 0 else ""
            tabs_html.append(
                f'<button class="pm-tab{active_class}" onclick="switchPMTab(this, \'{section_id}\')">{label}</button>'
            )

        yield f"""
    <div class="pm-panel" id="pm-panel">
        <div class="pm-panel-header">
            <h2>📸 Mídias do Perfil</h2>
            <div class="pm-summary">
                {f'<span>📷 {img_count} fotos</span>' if img_count else ''}
                {f'<span>🎬 {vid_count} vídeos</span>' if vid_count else ''}
                {f'<span>📱 {story_count} stories ({story_img} img, {story_vid} vid)</span>' if story_count else ''}
            </div>
            <button class="pm-close" onclick="toggleProfileMediaPanel()">✕</button>
            <div class="pm-tabs pm-tabs-scrollable">
                {''.join(tabs_html)}
            </div>
        </div>
        <div class="pm-panel-body">
        """

        for index, (section_id, _label, producer, grid_class) in enumerate(sections):
            display_style = "" if index == 0 else ' style="display:none"'
            yield f'<div class="pm-section" id="{section_id}"{display_style}><div class="{grid_class}">'
            yield from producer()
            yield "</div></div>"

        yield """
        </div>
    </div>"""

    def _iter_global_categories_panel(self):
        """Itera o painel agrupado de categorias genéricas."""
        categories = self.profile_media.generic_categories
        if not categories:
            return

        tabs_html = []
        for index, category in enumerate(categories):
            active_class = " active" if index == 0 else ""
            cat_id = f"gen-cat-{html.escape(category.category_id)}"
            tabs_html.append(
                f'<button class="pm-tab{active_class}" onclick="switchPMTab(this, \'{cat_id}\')">🗂️ {html.escape(category.category_name)}</button>'
            )

        yield f"""
            <div class="pm-panel global-cat-panel" id="global-cat-panel">
                <div class="pm-panel-header">
                    <h2>🗂️ Outras Categorias de Dados</h2>
                    <div class="pm-summary">
                        <span>🗂️ {len(categories)} categorias encontradas</span>
                    </div>
                    <button class="pm-close" onclick="toggleGlobalCatPanel()">✕</button>
                    <div class="pm-tabs pm-tabs-scrollable">
                        {''.join(tabs_html)}
                    </div>
                </div>
                <div class="pm-panel-body">
        """

        for index, category in enumerate(categories):
            cat_id = f"gen-cat-{html.escape(category.category_id)}"
            display_style = "" if index == 0 else ' style="display:none"'
            yield f'<div class="pm-section gen-cat-section" id="{cat_id}"{display_style}><div class="pm-gen-container">'
            for record in category.records:
                if not record.entries:
                    continue
                rows = []
                for entry in record.entries:
                    for key, value in entry.items():
                        key_display = html.escape(key)
                        value_display = html.escape(value).replace("\n", "<br>")
                        rows.append(f"<tr><th>{key_display}</th><td>{value_display}</td></tr>")
                if rows:
                    yield f'<table class="pm-gen-table">{"".join(rows)}</table>'
            yield "</div></div>"

        yield """
                </div>
            </div>"""

    def _get_full_template_skeleton(self, context: dict) -> str:
        """Retorna o template completo com placeholders para blocos grandes."""
        return self._get_full_template(
            self._SIDEBAR_TOKEN,
            self._CHATS_TOKEN,
            context["total_threads"],
            context["total_msgs"],
            context["min_date"],
            context["max_date"],
            self._GLOBAL_MEDIA_TOKEN,
            context["total_media"],
            self._STATS_TOKEN,
            context["stats_css"],
            context["stats_js"],
            self._PROFILE_MEDIA_TOKEN,
            context["profile_media_css"],
            context["profile_media_js"],
            self._GLOBAL_CATEGORIES_TOKEN,
            context["global_categories_buttons"],
        )
