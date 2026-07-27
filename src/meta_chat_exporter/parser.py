"""
Meta Platforms Chat Exporter - Parser HTML
Parser híbrido: BeautifulSoup para estrutura + regex para campos
"""

import html
import logging
import mmap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from meta_chat_exporter.constants import (
    RE_ACCOUNT_ID,
    RE_AI_STATUS,
    RE_AUTHOR,
    RE_BIDI_MARKS,
    RE_BODY,
    RE_CALL_DURATION,
    RE_CALL_MISSED,
    RE_CALL_TYPE,
    RE_DISAPPEARING,
    RE_DISAPPEARING_DURATION,
    RE_HTML_TAGS,
    RE_LINKED_MEDIA,
    RE_OPENING_DIV,
    RE_PAGE_BREAK_FULL,
    RE_PARTICIPANTS,
    RE_PAST_PARTICIPANTS,
    RE_PAYMENT,
    RE_READ_RECEIPTS,
    RE_SENT,
    RE_SHARE_TEXT,
    RE_SHARE_URL,
    RE_SUBSCRIPTION_TYPE,
    RE_SUBSCRIPTION_USERS,
    RE_TARGET,
    RE_THREAD,
    RE_THREAD_NAME,
    RE_USERNAME,
    get_timezone_offset,
)
from meta_chat_exporter.models import Attachment, Message, Participant, Thread
from meta_chat_exporter.utils import clean_message_body, get_file_type, is_safe_relative_path

logger = logging.getLogger(__name__)

# Acima deste tamanho, o arquivo é lido via mmap (apenas cabeçalho + seção de
# mensagens são decodificados) para reduzir o pico de memória em exports grandes.
LARGE_FILE_THRESHOLD_BYTES = 150 * 1024 * 1024

# Cadeia de encodings tentada ao decodificar HTML da Meta
_ENCODING_FALLBACKS = ("utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1")


@dataclass
class UnparsedItem:
    """Um item ignorado pelo parser durante o processamento (R34).

    Representa uma seção ou mensagem que o parser não conseguiu (ou optou por não)
    incorporar ao resultado final, junto do motivo e da origem para diagnóstico.
    """

    # Tipo do item ignorado: "section" (seção/conversa) ou "message" (mensagem)
    kind: str
    # Motivo legível pelo qual o item foi ignorado
    reason: str
    # Arquivo de origem onde o item foi encontrado
    source_file: str
    # Detalhe opcional (ex.: id da thread, trecho do conteúdo)
    detail: str = ""


@dataclass
class UnparsedReport:
    """Coletor de seções/mensagens ignoradas durante o parse (R34).

    Acumula itens ignorados sem interromper o fluxo de parsing e expõe a
    contagem total ao final. Quando nenhum item é ignorado, ``count == 0`` e
    nenhum erro é produzido.
    """

    items: list[UnparsedItem] = field(default_factory=list)

    def record_section(self, reason: str, source_file: str, detail: str = "") -> None:
        """Registra uma seção (ou conversa) ignorada."""
        self.items.append(UnparsedItem("section", reason, source_file, detail))

    def record_message(self, reason: str, source_file: str, detail: str = "") -> None:
        """Registra uma mensagem ignorada."""
        self.items.append(UnparsedItem("message", reason, source_file, detail))

    @property
    def count(self) -> int:
        """Número total de itens não parseados (seções + mensagens)."""
        return len(self.items)

    @property
    def section_count(self) -> int:
        """Número de seções ignoradas."""
        return sum(1 for item in self.items if item.kind == "section")

    @property
    def message_count(self) -> int:
        """Número de mensagens ignoradas."""
        return sum(1 for item in self.items if item.kind == "message")

    def clear(self) -> None:
        """Reinicia o relatório, descartando os itens acumulados."""
        self.items.clear()


class MetaRecordsParser:
    """Parser híbrido: BeautifulSoup para estrutura + regex para campos"""

    def __init__(self, html_path: str, log_callback=None):
        self.html_path = Path(html_path)
        self.base_dir = self.html_path.parent
        self.source_filename = self.html_path.name
        self.threads: list[Thread] = []
        self.owner_username: str = ""
        self.owner_id: str = ""
        self.log = log_callback or (lambda x: None)
        self.parse_stats: dict[str, int] = self._new_stats()
        self.unparsed = UnparsedReport()
        if BS4_AVAILABLE:
            logger.debug("Parser BS4 inicializado com source_filename: %s", self.source_filename)
        else:
            logger.debug(
                "BS4 indisponível, usando modo regex puro. source_filename: %s",
                self.source_filename,
            )

    @staticmethod
    def _new_stats() -> dict[str, int]:
        """Cria o dicionário de estatísticas de parsing (falhas observáveis)."""
        return {
            "threads_found": 0,
            "threads_kept": 0,
            "threads_discarded_empty": 0,
            "messages_parsed": 0,
            "messages_timestamp_errors": 0,
            "attachments_rejected_traversal": 0,
            "call_duration_errors": 0,
        }

    def parse(self, progress_callback=None) -> list[Thread]:
        """Parseia o arquivo HTML e retorna lista de threads"""
        logger.debug("Abrindo arquivo: %s", self.html_path)
        self.log(f"📂 Abrindo arquivo: {self.html_path.name}")
        self.parse_stats = self._new_stats()
        self.unparsed = UnparsedReport()

        # Validar arquivo
        if not self.html_path.exists():
            logger.error("Arquivo não encontrado: %s", self.html_path)
            self.log(f"❌ Arquivo não encontrado: {self.html_path.name}")
            return []

        if self.html_path.stat().st_size == 0:
            logger.error("Arquivo vazio: %s", self.html_path)
            self.log(f"❌ Arquivo vazio: {self.html_path.name}")
            return []

        # Determinar estratégia de leitura conforme o tamanho do arquivo
        file_size = self.html_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        logger.debug("Tamanho do arquivo: %.2f MB", file_size_mb)
        self.log(f"📊 Tamanho do arquivo: {file_size_mb:.2f} MB")

        if file_size > LARGE_FILE_THRESHOLD_BYTES:
            logger.info(
                "Arquivo grande (%.0f MB): leitura via mmap para reduzir memória", file_size_mb
            )
            self.log("🧠 Arquivo grande: leitura otimizada (mmap) para economizar memória")
            header, section = self._read_relevant_via_mmap()
            if header is None:
                # Fallback: leitura completa em memória
                logger.warning("mmap indisponível/falhou, usando leitura completa")
                content = self._read_file_safe()
                if content is None:
                    return []
                header = content[:50000]
                section = self._extract_section_str(content)
                del content
        else:
            content = self._read_file_safe()
            if content is None:
                return []
            header = content[:50000]
            section = self._extract_section_str(content)
            del content  # Liberar memória

        # Extrair owner info
        self._extract_owner_info(header)

        # Verificar a seção de Unified Messages
        logger.debug("Procurando seção Unified Messages...")
        self.log("🔍 Procurando seção Unified Messages...")
        if section is None:
            logger.debug(
                "Seção Unified Messages não encontrada em %s (normal se o arquivo não contém mensagens)",
                self.source_filename,
            )
            self.unparsed.record_section("Seção Unified Messages ausente", self.source_filename)
            self.log(
                f"ℹ️ {self.source_filename}: sem seção Unified Messages (buscando em outros arquivos...)"
            )
            return []

        logger.debug("Seção encontrada!")
        self.log("✅ Seção encontrada!")
        section_size_mb = len(section) / (1024 * 1024)
        logger.debug("Tamanho da seção: %.2f MB", section_size_mb)
        self.log(f"📏 Tamanho da seção: {section_size_mb:.2f} MB")

        # Limpar quebras de página do HTML antes do parsing
        logger.debug("Removendo quebras de página...")
        self.log("🧹 Removendo quebras de página...")

        def _balanced_page_break_replace(match):
            """Remove page break balancing closing/opening divs."""
            closing_count = match.group(1).count("</div>")
            opening_divs = RE_OPENING_DIV.findall(match.group(2))
            opening_count = len(opening_divs)
            n = min(closing_count, opening_count)
            # Keep any excess unbalanced divs
            excess_closing = "</div>" * (closing_count - n)
            excess_opening = "".join(opening_divs[n:])
            return excess_closing + excess_opening

        section = RE_PAGE_BREAK_FULL.sub(_balanced_page_break_replace, section)
        logger.debug("Tamanho após limpeza: %.2f MB", len(section) / (1024 * 1024))

        # Parse dos threads
        logger.debug("Iniciando parse de threads...")
        self._parse_threads_fast(section, progress_callback)
        logger.debug("Parse concluído. Total: %d threads", len(self.threads))

        # Verificar source_file das mensagens
        total_msgs = sum(len(t.messages) for t in self.threads)
        sample_sources = set()
        for t in self.threads[:5]:
            for m in t.messages[:3]:
                sample_sources.add(m.source_file)
        logger.debug(
            "Total de mensagens: %d, source_files encontrados: %s", total_msgs, sample_sources
        )
        self.log(f"📄 Arquivo: {self.source_filename} → {total_msgs} msgs")

        self._log_parse_stats()

        return self.threads

    def _log_parse_stats(self) -> None:
        """Loga um resumo das anomalias do parse (falhas antes silenciosas)."""
        st = self.parse_stats
        anomalies = (
            st["threads_discarded_empty"]
            + st["messages_timestamp_errors"]
            + st["attachments_rejected_traversal"]
            + st["call_duration_errors"]
        )
        if anomalies:
            logger.info(
                "Resumo do parse de %s: %d/%d threads mantidas | %d vazias descartadas | "
                "%d timestamps inválidos | %d anexos rejeitados (traversal) | "
                "%d durações de chamada inválidas",
                self.source_filename,
                st["threads_kept"],
                st["threads_found"],
                st["threads_discarded_empty"],
                st["messages_timestamp_errors"],
                st["attachments_rejected_traversal"],
                st["call_duration_errors"],
            )
            if st["attachments_rejected_traversal"]:
                self.log(
                    f"⚠️ {st['attachments_rejected_traversal']} anexo(s) rejeitado(s) "
                    "por path traversal"
                )

        # Relatório de conteúdo não parseado (R34): reportar a contagem ao final.
        # Sem itens ignorados, count == 0 e nenhuma mensagem de erro é emitida.
        unparsed_count = self.unparsed.count
        if unparsed_count:
            logger.info(
                "Conteúdo não parseado em %s: %d item(ns) ignorado(s) "
                "(%d seção(ões), %d mensagem(ns))",
                self.source_filename,
                unparsed_count,
                self.unparsed.section_count,
                self.unparsed.message_count,
            )
            self.log(
                f"⚠️ {unparsed_count} item(ns) não parseado(s) ignorado(s) "
                f"em {self.source_filename}"
            )

    def _extract_section_str(self, content: str) -> str | None:
        """Localiza e retorna a seção Unified Messages (ou None se ausente)."""
        start = content.find('id="property-unified_messages"')
        if start == -1:
            start = content.find('id="property-threads_unified_messages"')
        if start == -1:
            return None
        end = content.find('id="property-', start + 30)
        if end == -1:
            end = len(content)
        return content[start:end]

    @staticmethod
    def _decode_bytes(raw: bytes) -> str:
        """Decodifica bytes com a mesma cadeia de fallback de encoding."""
        for encoding in _ENCODING_FALLBACKS:
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        # latin-1 nunca falha, mas garantimos um retorno mesmo assim
        return raw.decode("utf-8", errors="replace")

    def _read_relevant_via_mmap(self) -> tuple[str | None, str | None]:
        """Extrai apenas cabeçalho + seção de mensagens via mmap (arquivos grandes).

        Decodifica somente as fatias necessárias, reduzindo o pico de memória.
        Retorna (header, section):
          - header None  -> falha de mmap (o chamador deve usar leitura completa);
          - section None -> seção Unified Messages ausente no arquivo.
        """
        markers = (
            b'id="property-unified_messages"',
            b'id="property-threads_unified_messages"',
        )
        try:
            with (
                open(self.html_path, "rb") as f,
                mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm,
            ):
                header = self._decode_bytes(mm[:50000])
                start = -1
                for marker in markers:
                    start = mm.find(marker)
                    if start != -1:
                        break
                if start == -1:
                    return header, None
                end = mm.find(b'id="property-', start + 30)
                if end == -1:
                    end = mm.size()
                section = self._decode_bytes(mm[start:end])
                return header, section
        except (OSError, ValueError) as e:
            logger.error("Erro no mmap de %s: %s", self.html_path, e)
            return None, None

    def _read_file_safe(self) -> str | None:
        """Lê arquivo HTML com fallback de encoding"""
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(self.html_path, encoding=encoding, buffering=1024 * 1024) as f:
                    content = f.read()
                if encoding != "utf-8":
                    logger.warning(
                        "Arquivo lido com encoding alternativo: %s (pode haver caracteres incorretos)",
                        encoding,
                    )
                    self.log(f"⚠️ Encoding não-UTF-8 utilizado: {encoding}")
                return content
            except UnicodeDecodeError:
                logger.debug("Falha com encoding %s, tentando próximo...", encoding)
                continue
            except PermissionError:
                logger.error("Sem permissão para ler: %s", self.html_path)
                self.log(f"❌ Sem permissão para ler: {self.html_path.name}")
                return None
            except OSError as e:
                logger.error("Erro de I/O ao ler %s: %s", self.html_path, e)
                self.log(f"❌ Erro ao ler arquivo: {e}")
                return None

        logger.error("Nenhum encoding funcionou para: %s", self.html_path)
        self.log(f"❌ Não foi possível decodificar: {self.html_path.name}")
        return None

    def _extract_owner_info(self, content: str):
        """Extrai informações do dono da conta (BS4 + regex fallback)"""
        header = content[:50000]

        if BS4_AVAILABLE:
            try:
                soup = BeautifulSoup(header, "html.parser")
                # Procurar "Account Identifier" no texto
                for div in soup.find_all("div", class_="t"):
                    text = div.get_text(separator=" ", strip=True)
                    if "Account Identifier" in text:
                        value_div = div.find("div", class_="m")
                        if value_div:
                            inner = value_div.find("div")
                            if inner:
                                self.owner_username = inner.get_text(strip=True)
                                self.log(f"👤 Usuário identificado: {self.owner_username}")
                    elif "Target" in text and not self.owner_id:
                        value_div = div.find("div", class_="m")
                        if value_div:
                            inner = value_div.find("div")
                            if inner:
                                val = inner.get_text(strip=True)
                                if val.isdigit():
                                    self.owner_id = val
                                    self.log(f"🆔 ID da conta: {self.owner_id}")
                del soup
                if self.owner_username:
                    return
            except Exception as e:
                logger.debug("BS4 falhou para owner info, usando regex: %s", e)

        # Fallback para regex
        match = RE_ACCOUNT_ID.search(header)
        if match:
            self.owner_username = match.group(1).strip()
            self.log(f"👤 Usuário identificado: {self.owner_username}")

        match = RE_TARGET.search(header)
        if match:
            self.owner_id = match.group(1).strip()
            self.log(f"🆔 ID da conta: {self.owner_id}")

    def _parse_threads_fast(self, section: str, progress_callback=None):
        """Parseia threads de forma otimizada"""
        logger.debug("Identificando conversas com regex...")
        self.log("🔄 Identificando conversas...")
        thread_matches = list(RE_THREAD.finditer(section))
        total = len(thread_matches)
        logger.debug("Encontradas %d conversas", total)
        self.log(f"📱 Encontradas {total} conversas")
        self.parse_stats["threads_found"] = total

        for i, match in enumerate(thread_matches):
            thread_id = match.group(1)

            start_pos = match.start()
            end_pos = thread_matches[i + 1].start() if i + 1 < total else len(section)

            thread_text = section[start_pos:end_pos]
            thread = self._parse_single_thread_fast(thread_id, thread_text, i + 1, total)

            if thread and thread.messages:
                thread.base_dir = self.base_dir
                self.threads.append(thread)
                self.parse_stats["threads_kept"] += 1
                if i < 5 or i % 50 == 0:
                    logger.debug(
                        "Thread %d/%d: ID=%s, msgs=%d",
                        i + 1,
                        total,
                        thread_id,
                        len(thread.messages),
                    )
            else:
                self.parse_stats["threads_discarded_empty"] += 1
                self.unparsed.record_section(
                    "Conversa sem mensagens", self.source_filename, detail=thread_id
                )
                logger.debug("Thread %s descartada: sem mensagens", thread_id)

            if progress_callback and total > 0:
                progress_callback((i + 1) / total)

    def _parse_single_thread_fast(
        self, thread_id: str, thread_html: str, current: int, total: int
    ) -> Thread | None:
        """Parseia um único thread de forma otimizada"""
        thread = Thread(thread_id=thread_id, thread_name="", participants=[])

        # Participantes
        match = RE_PARTICIPANTS.search(thread_html)
        if match:
            thread.participants = [Participant(*t) for t in RE_USERNAME.findall(match.group(1))]

        # AI status
        match = RE_AI_STATUS.search(thread_html)
        if match:
            thread.ai_enabled = match.group(1).lower() == "true"

        # Thread Name
        match = RE_THREAD_NAME.search(thread_html)
        if match:
            thread.thread_name = clean_message_body(html.unescape(match.group(1).strip()))

        # Past Participants
        match = RE_PAST_PARTICIPANTS.search(thread_html)
        if match:
            thread.past_participants = [
                Participant(*t) for t in RE_USERNAME.findall(match.group(1))
            ]

        # Read Receipts
        match = RE_READ_RECEIPTS.search(thread_html)
        if match:
            thread.read_receipts = match.group(1).strip()

        # Mensagens
        thread.messages = self._parse_messages_fast(thread_html)

        # Log do progresso
        if thread.messages:
            participants_str = ", ".join([p[0] for p in thread.participants[:2]])
            if len(thread.participants) > 2:
                participants_str += f" +{len(thread.participants)-2}"
            self.log(f"  [{current}/{total}] 💬 {len(thread.messages)} msgs - {participants_str}")

        return thread

    def _parse_messages_fast(self, thread_html: str) -> list[Message]:
        """Parseia mensagens de forma otimizada"""
        messages = []

        author_positions = [m.start() for m in RE_AUTHOR.finditer(thread_html)]
        total = len(author_positions)

        for i, start_pos in enumerate(author_positions):
            end_pos = author_positions[i + 1] if i + 1 < total else len(thread_html)
            msg_text = thread_html[start_pos:end_pos]

            msg = self._parse_single_message_fast(msg_text)
            if msg:
                messages.append(msg)
            else:
                # Mensagem ignorada: bloco sem autor reconhecível (R34)
                self.unparsed.record_message(
                    "Mensagem sem autor reconhecível", self.source_filename
                )

        messages.sort(key=lambda m: m.sent or datetime.min)

        self.parse_stats["messages_parsed"] += len(messages)

        return messages

    def _parse_single_message_fast(self, msg_html: str) -> Message | None:
        """Parseia uma mensagem de forma otimizada"""
        match = RE_AUTHOR.search(msg_html)
        if not match:
            return None

        author = clean_message_body(match.group(1).strip())
        platform = match.group(2).strip()
        author_id = match.group(3).strip()

        sent = None
        match = RE_SENT.search(msg_html)
        if match:
            try:
                sent_utc = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S UTC")
                sent = sent_utc + get_timezone_offset()
            except ValueError:
                self.parse_stats["messages_timestamp_errors"] += 1
                logger.debug("Timestamp inválido ignorado: %r", match.group(1))

        body = ""
        is_edited = False
        match = RE_BODY.search(msg_html)
        if match:
            raw_body = match.group(1)
            # Remove any residual HTML tags from the body content
            raw_body = RE_HTML_TAGS.sub("", raw_body)
            body = html.unescape(raw_body.strip())
            body = clean_message_body(body)
            # v5.2: limpar marcas bidi unicode (FSI/PDI) que envolvem @mentions em grupos
            body = RE_BIDI_MARKS.sub("", body)
            # Detect edited messages
            if body.endswith("(edited)"):
                is_edited = True
                body = body[: -len("(edited)")].rstrip()

        removed_by_sender = "Removed by Sender" in msg_html

        disappearing = False
        match = RE_DISAPPEARING.search(msg_html)
        if match:
            disappearing = match.group(1) == "On"

        disappearing_duration = ""
        match = RE_DISAPPEARING_DURATION.search(msg_html)
        if match:
            disappearing_duration = match.group(1).strip()

        attachments = []
        for local_path in RE_LINKED_MEDIA.findall(msg_html):
            local_path = local_path.strip()
            # Limpar HTML residual do caminho
            local_path = clean_message_body(local_path)
            if not local_path:
                continue
            # Rejeitar paths inseguros (traversal "../" ou caminhos absolutos)
            if not is_safe_relative_path(local_path):
                self.parse_stats["attachments_rejected_traversal"] += 1
                logger.warning("Path inseguro detectado, ignorando anexo: %s", local_path)
                continue
            file_type = get_file_type(local_path)
            attachments.append(
                Attachment(
                    filename=Path(local_path).name,
                    file_type=file_type,
                    size=0,
                    url="",
                    local_path=local_path,
                )
            )

        share_url = None
        share_text = None
        if 'Share<div class="m">' in msg_html:
            match = RE_SHARE_URL.search(msg_html)
            if match:
                share_url = html.unescape(match.group(1).strip())
            match = RE_SHARE_TEXT.search(msg_html)
            if match:
                share_text = html.unescape(match.group(1).strip())
            # v5.2: limpar marcas bidi do share_text também
            if share_text:
                share_text = RE_BIDI_MARKS.sub("", share_text)
            # Phase 6.2: descartar shares vazios (Date Unknown sem URL nem Text significativos)
            if (not share_url or not share_url.strip()) and (
                not share_text or not share_text.strip()
            ):
                share_url = None
                share_text = None

        is_call = "Call Record" in msg_html
        call_type = ""
        call_duration = 0
        call_missed = False

        if is_call:
            match = RE_CALL_TYPE.search(msg_html)
            if match:
                call_type = match.group(1).strip()
            match = RE_CALL_DURATION.search(msg_html)
            if match:
                try:
                    call_duration = int(match.group(1))
                except ValueError:
                    self.parse_stats["call_duration_errors"] += 1
                    logger.debug("Duração de chamada inválida ignorada: %r", match.group(1))
            match = RE_CALL_MISSED.search(msg_html)
            if match:
                call_missed = match.group(1).lower() == "true"

        # Subscription Events (entrada/saída de grupo)
        subscription_event = ""
        subscription_users: list[str] = []
        if "Subscription Event" in msg_html:
            match = RE_SUBSCRIPTION_TYPE.search(msg_html)
            if match:
                subscription_event = match.group(1).strip().lower()
            match = RE_SUBSCRIPTION_USERS.search(msg_html)
            if match:
                subscription_users = [u.strip() for u in match.group(1).split(",") if u.strip()]

        # Detecção de reações ("Liked a message", "Reacted ... to your message")
        is_reaction = False
        if body:
            body_lower = body.lower()
            if (
                "liked a message" in body_lower
                or "reacted" in body_lower
                and "to your message" in body_lower
            ):
                is_reaction = True

        # Detecção de pagamentos
        has_payment = bool(RE_PAYMENT.search(msg_html))

        return Message(
            author=author,
            author_id=author_id,
            platform=platform,
            sent=sent,
            body=body,
            disappearing=disappearing,
            disappearing_duration=disappearing_duration,
            attachments=attachments,
            share_url=share_url,
            share_text=share_text,
            is_call=is_call,
            call_type=call_type,
            call_duration=call_duration,
            call_missed=call_missed,
            removed_by_sender=removed_by_sender,
            source_file=self.source_filename,
            is_reaction=is_reaction,
            subscription_event=subscription_event,
            subscription_users=subscription_users,
            has_payment=has_payment,
            is_edited=is_edited,
        )
