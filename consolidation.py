"""
Meta Platforms Chat Exporter - Consolidação de Threads
Módulo compartilhado para consolidar threads de múltiplos arquivos HTML,
eliminando duplicatas e mesclando dados.
"""

import hashlib
import logging
from datetime import datetime
from typing import List

from models import Thread, Message

logger = logging.getLogger(__name__)


def get_message_signature(msg: Message) -> tuple:
    """Gera assinatura única para detectar duplicatas de mensagens.

    A assinatura é baseada em: autor, timestamp, hash do corpo completo,
    nomes de anexos, flag de chamada e URL de compartilhamento.
    """
    timestamp = msg.sent.strftime("%Y%m%d%H%M%S") if msg.sent else "no_date"
    body_text = (msg.body or "").strip()
    body_hash = hashlib.md5(body_text.encode("utf-8")).hexdigest() if body_text else ""
    attachments = tuple(att.filename for att in msg.attachments) if msg.attachments else ()
    return (msg.author_id, timestamp, body_hash, attachments, msg.is_call, msg.share_url or "")


def consolidate_threads(all_threads: List[Thread],
                        log_callback=None) -> List[Thread]:
    """Consolida threads de múltiplos arquivos HTML.

    Mescla threads com mesmo thread_id, remove mensagens duplicadas
    via assinatura, e prioriza 'records.html' como fonte.

    Args:
        all_threads: Lista de threads de todos os arquivos parseados.
        log_callback: Callback opcional para mensagens de log (ex: GUI ou print).

    Returns:
        Lista de threads consolidados, ordenados cronologicamente.
    """
    threads_dict = {}

    # Debug: verificar source_files
    source_files_found = set()
    source_file_counts = {}
    for thread in all_threads:
        for msg in thread.messages:
            if msg.source_file:
                source_files_found.add(msg.source_file)
                source_file_counts[msg.source_file] = source_file_counts.get(msg.source_file, 0) + 1

    logger.debug("Arquivos de origem: %s", source_files_found)
    for sf, count in sorted(source_file_counts.items()):
        logger.debug("   %s: %d mensagens", sf, count)

    if log_callback:
        log_callback(f"📁 Origens: {', '.join(source_files_found) if source_files_found else 'Nenhuma'}")

    for thread in all_threads:
        if thread.thread_id in threads_dict:
            existing = threads_dict[thread.thread_id]

            # Criar conjunto de assinaturas para detectar duplicatas
            existing_sigs = set()
            sig_to_msg = {}
            for msg in existing.messages:
                sig = get_message_signature(msg)
                existing_sigs.add(sig)
                sig_to_msg[sig] = msg

            new_msgs_count = 0
            for msg in thread.messages:
                sig = get_message_signature(msg)
                if sig not in existing_sigs:
                    existing.messages.append(msg)
                    existing_sigs.add(sig)
                    sig_to_msg[sig] = msg
                    new_msgs_count += 1
                else:
                    # Priorizar records.html como origem
                    existing_msg = sig_to_msg.get(sig)
                    if existing_msg and msg.source_file:
                        if 'records' in msg.source_file.lower() and 'records' not in existing_msg.source_file.lower():
                            existing_msg.source_file = msg.source_file

            if new_msgs_count > 0:
                logger.debug("Thread %s: +%d novas mensagens", thread.thread_id[:8], new_msgs_count)

            # Atualizar participantes (união)
            existing_participants = set(tuple(p) for p in existing.participants)
            for p in thread.participants:
                if tuple(p) not in existing_participants:
                    existing.participants.append(p)

            # Atualizar past_participants (união)
            if hasattr(thread, 'past_participants') and thread.past_participants:
                existing_past = set(tuple(p) for p in existing.past_participants)
                for p in thread.past_participants:
                    if tuple(p) not in existing_past:
                        existing.past_participants.append(p)

            if not existing.thread_name and thread.thread_name:
                existing.thread_name = thread.thread_name

            if thread.base_dir:
                existing.base_dir = thread.base_dir

        else:
            threads_dict[thread.thread_id] = thread

    # Ordenar mensagens cronologicamente
    for thread in threads_dict.values():
        thread.messages.sort(key=lambda m: m.sent or datetime.min)

    consolidated = list(threads_dict.values())

    total_original = len(all_threads)
    total_consolidated = len(consolidated)
    if total_original != total_consolidated:
        logger.debug("%d threads → %d threads únicos", total_original, total_consolidated)
        if log_callback:
            log_callback(f"🔗 Consolidado: {total_original} → {total_consolidated} threads únicos")

    # Contagem por origem após consolidação
    origin_counts = {}
    for thread in consolidated:
        for msg in thread.messages:
            origin = msg.source_file or "Desconhecido"
            origin_counts[origin] = origin_counts.get(origin, 0) + 1

    logger.debug("Mensagens por origem após consolidação:")
    for origin, count in sorted(origin_counts.items(), key=lambda x: -x[1]):
        logger.debug("   %s: %d mensagens", origin, count)

    return consolidated
