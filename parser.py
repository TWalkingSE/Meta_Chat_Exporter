"""
Meta Platforms Chat Exporter - Parser HTML
Parser híbrido: BeautifulSoup para estrutura + regex para campos
"""

import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

try:
    from bs4 import BeautifulSoup, SoupStrainer
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from constants import (
    RE_THREAD, RE_ACCOUNT_ID, RE_TARGET, RE_PARTICIPANTS,
    RE_USERNAME, RE_AI_STATUS, RE_THREAD_NAME, RE_AUTHOR, RE_SENT,
    RE_BODY, RE_DISAPPEARING, RE_DISAPPEARING_DURATION, RE_LINKED_MEDIA,
    RE_SHARE_URL, RE_SHARE_TEXT, RE_CALL_TYPE, RE_CALL_DURATION,
    RE_CALL_MISSED, RE_PAGE_BREAK_FULL, RE_OPENING_DIV, RE_HTML_TAGS,
    RE_SUBSCRIPTION_TYPE, RE_SUBSCRIPTION_USERS, RE_PAST_PARTICIPANTS,
    RE_READ_RECEIPTS, RE_PAYMENT, RE_BIDI_MARKS, RE_SHARE_EMPTY,
    get_timezone_offset
)
import constants
from models import Attachment, Message, Thread, Participant
from utils import clean_message_body, get_file_type

logger = logging.getLogger(__name__)


class MetaRecordsParser:
    """Parser híbrido: BeautifulSoup para estrutura + regex para campos"""

    def __init__(self, html_path: str, log_callback=None):
        self.html_path = Path(html_path)
        self.base_dir = self.html_path.parent
        self.source_filename = self.html_path.name
        self.threads: List[Thread] = []
        self.owner_username: str = ""
        self.owner_id: str = ""
        self.log = log_callback or (lambda x: None)
        if BS4_AVAILABLE:
            logger.debug("Parser BS4 inicializado com source_filename: %s", self.source_filename)
        else:
            logger.debug("BS4 indisponível, usando modo regex puro. source_filename: %s", self.source_filename)

    def parse(self, progress_callback=None) -> List[Thread]:
        """Parseia o arquivo HTML e retorna lista de threads"""
        logger.debug("Abrindo arquivo: %s", self.html_path)
        self.log(f"📂 Abrindo arquivo: {self.html_path.name}")

        # Validar arquivo
        if not self.html_path.exists():
            logger.error("Arquivo não encontrado: %s", self.html_path)
            self.log(f"❌ Arquivo não encontrado: {self.html_path.name}")
            return []

        if self.html_path.stat().st_size == 0:
            logger.error("Arquivo vazio: %s", self.html_path)
            self.log(f"❌ Arquivo vazio: {self.html_path.name}")
            return []

        # Ler arquivo com fallback de encoding
        content = self._read_file_safe()

        if content is None:
            return []

        file_size_mb = len(content) / (1024 * 1024)
        logger.debug("Tamanho do arquivo: %.2f MB", file_size_mb)
        self.log(f"📊 Tamanho do arquivo: {file_size_mb:.2f} MB")

        # Extrair owner info
        self._extract_owner_info(content)

        # Encontrar a seção de Unified Messages
        logger.debug("Procurando seção Unified Messages...")
        self.log("🔍 Procurando seção Unified Messages...")
        start = content.find('id="property-unified_messages"')
        if start == -1:
            # Tentar também threads_unified_messages (Threads)
            start = content.find('id="property-threads_unified_messages"')
        logger.debug("Posição da seção: %d", start)
        if start == -1:
            logger.debug("Seção Unified Messages não encontrada em %s (normal se o arquivo não contém mensagens)", self.source_filename)
            self.log(f"ℹ️ {self.source_filename}: sem seção Unified Messages (buscando em outros arquivos...)")
            return []

        logger.debug("Seção encontrada!")
        self.log("✅ Seção encontrada!")

        # Encontrar o fim da seção
        end = content.find('id="property-', start + 30)
        if end == -1:
            end = len(content)
        logger.debug("Seção de %d a %d (%d caracteres)", start, end, end - start)

        section = content[start:end]
        section_size_mb = len(section) / (1024 * 1024)
        logger.debug("Tamanho da seção: %.2f MB", section_size_mb)
        self.log(f"📏 Tamanho da seção: {section_size_mb:.2f} MB")

        del content  # Liberar memória

        # Limpar quebras de página do HTML antes do parsing
        logger.debug("Removendo quebras de página...")
        self.log("🧹 Removendo quebras de página...")

        def _balanced_page_break_replace(match):
            """Remove page break balancing closing/opening divs."""
            closing_count = match.group(1).count('</div>')
            opening_divs = RE_OPENING_DIV.findall(match.group(2))
            opening_count = len(opening_divs)
            n = min(closing_count, opening_count)
            # Keep any excess unbalanced divs
            excess_closing = '</div>' * (closing_count - n)
            excess_opening = ''.join(opening_divs[n:])
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
        logger.debug("Total de mensagens: %d, source_files encontrados: %s", total_msgs, sample_sources)
        self.log(f"📄 Arquivo: {self.source_filename} → {total_msgs} msgs")

        return self.threads

    def _read_file_safe(self) -> Optional[str]:
        """Lê arquivo HTML com fallback de encoding"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                with open(self.html_path, 'r', encoding=encoding, buffering=1024*1024) as f:
                    content = f.read()
                if encoding != 'utf-8':
                    logger.warning("Arquivo lido com encoding alternativo: %s (pode haver caracteres incorretos)", encoding)
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
                soup = BeautifulSoup(header, 'html.parser')
                # Procurar "Account Identifier" no texto
                for div in soup.find_all('div', class_='t'):
                    text = div.get_text(separator=' ', strip=True)
                    if 'Account Identifier' in text:
                        value_div = div.find('div', class_='m')
                        if value_div:
                            inner = value_div.find('div')
                            if inner:
                                self.owner_username = inner.get_text(strip=True)
                                self.log(f"👤 Usuário identificado: {self.owner_username}")
                    elif 'Target' in text and not self.owner_id:
                        value_div = div.find('div', class_='m')
                        if value_div:
                            inner = value_div.find('div')
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

        for i, match in enumerate(thread_matches):
            thread_id = match.group(1)

            start_pos = match.start()
            end_pos = thread_matches[i + 1].start() if i + 1 < total else len(section)

            thread_text = section[start_pos:end_pos]
            thread = self._parse_single_thread_fast(thread_id, thread_text, i + 1, total)

            if thread and thread.messages:
                thread.base_dir = self.base_dir
                self.threads.append(thread)
                if i < 5 or i % 50 == 0:
                    logger.debug("Thread %d/%d: ID=%s, msgs=%d", i + 1, total, thread_id, len(thread.messages))

            if progress_callback and total > 0:
                progress_callback((i + 1) / total)

    def _parse_single_thread_fast(self, thread_id: str, thread_html: str,
                                   current: int, total: int) -> Optional[Thread]:
        """Parseia um único thread de forma otimizada"""
        thread = Thread(
            thread_id=thread_id,
            thread_name="",
            participants=[]
        )

        # Participantes
        match = RE_PARTICIPANTS.search(thread_html)
        if match:
            thread.participants = [Participant(*t) for t in RE_USERNAME.findall(match.group(1))]

        # AI status
        match = RE_AI_STATUS.search(thread_html)
        if match:
            thread.ai_enabled = match.group(1).lower() == 'true'

        # Thread Name
        match = RE_THREAD_NAME.search(thread_html)
        if match:
            thread.thread_name = clean_message_body(html.unescape(match.group(1).strip()))

        # Past Participants
        match = RE_PAST_PARTICIPANTS.search(thread_html)
        if match:
            thread.past_participants = [Participant(*t) for t in RE_USERNAME.findall(match.group(1))]

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

    def _parse_messages_fast(self, thread_html: str) -> List[Message]:
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

        messages.sort(key=lambda m: m.sent or datetime.min)

        return messages

    def _parse_single_message_fast(self, msg_html: str) -> Optional[Message]:
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
                sent_utc = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S UTC')
                sent = sent_utc + get_timezone_offset()
            except ValueError:
                pass

        body = ""
        is_edited = False
        match = RE_BODY.search(msg_html)
        if match:
            raw_body = match.group(1)
            # Remove any residual HTML tags from the body content
            raw_body = RE_HTML_TAGS.sub('', raw_body)
            body = html.unescape(raw_body.strip())
            body = clean_message_body(body)
            # v5.2: limpar marcas bidi unicode (FSI/PDI) que envolvem @mentions em grupos
            body = RE_BIDI_MARKS.sub('', body)
            # Detect edited messages
            if body.endswith('(edited)'):
                is_edited = True
                body = body[:-len('(edited)')].rstrip()

        removed_by_sender = 'Removed by Sender' in msg_html

        disappearing = False
        match = RE_DISAPPEARING.search(msg_html)
        if match:
            disappearing = match.group(1) == 'On'

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
            # Rejeitar paths com traversal (../)
            if '..' in local_path:
                logger.warning("Path traversal detectado, ignorando anexo: %s", local_path)
                continue
            file_type = get_file_type(local_path)
            attachments.append(Attachment(
                filename=Path(local_path).name,
                file_type=file_type,
                size=0,
                url="",
                local_path=local_path
            ))

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
                share_text = RE_BIDI_MARKS.sub('', share_text)
            # Phase 6.2: descartar shares vazios (Date Unknown sem URL nem Text significativos)
            if (not share_url or not share_url.strip()) and (not share_text or not share_text.strip()):
                share_url = None
                share_text = None

        is_call = 'Call Record' in msg_html
        call_type = ""
        call_duration = 0
        call_missed = False

        if is_call:
            match = RE_CALL_TYPE.search(msg_html)
            if match:
                call_type = match.group(1).strip()
            match = RE_CALL_DURATION.search(msg_html)
            if match:
                call_duration = int(match.group(1))
            match = RE_CALL_MISSED.search(msg_html)
            if match:
                call_missed = match.group(1).lower() == 'true'

        # Subscription Events (entrada/saída de grupo)
        subscription_event = ""
        subscription_users: List[str] = []
        if 'Subscription Event' in msg_html:
            match = RE_SUBSCRIPTION_TYPE.search(msg_html)
            if match:
                subscription_event = match.group(1).strip().lower()
            match = RE_SUBSCRIPTION_USERS.search(msg_html)
            if match:
                subscription_users = [u.strip() for u in match.group(1).split(',') if u.strip()]

        # Detecção de reações ("Liked a message", "Reacted ... to your message")
        is_reaction = False
        if body:
            body_lower = body.lower()
            if ('liked a message' in body_lower or
                'reacted' in body_lower and 'to your message' in body_lower):
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
            is_edited=is_edited
        )
