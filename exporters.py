"""
Meta Platforms Chat Exporter - Exportadores JSON e CSV
Exporta conversas para formatos estruturados
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from models import Thread, Message, Attachment
from stats import ChatStatistics

logger = logging.getLogger(__name__)

# Caracteres que podem acionar execução de fórmulas em planilhas
_CSV_INJECTION_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _sanitize_csv_value(value) -> str:
    """Sanitiza valor para evitar CSV injection (formula injection) em Excel/Sheets."""
    if isinstance(value, str) and value and value[0] in _CSV_INJECTION_CHARS:
        return "'" + value
    return value


class JSONExporter:
    """Exporta conversas para formato JSON"""

    def __init__(self, threads: List[Thread], owner_username: str = "", owner_id: str = "",
                 base_dir=None, profile_media=None):
        self.threads = threads
        self.owner_username = owner_username
        self.owner_id = owner_id
        self.base_dir = base_dir
        self.profile_media = profile_media

    def export(self, output_path: Path, include_stats: bool = True) -> Path:
        """Exporta todas as conversas para JSON"""
        logger.info("Exportando para JSON: %s", output_path)

        # Verificar se o diretório de destino é gravável
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "meta": {
                "exportado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_conversas": len(self.threads),
                "total_mensagens": sum(len(t.messages) for t in self.threads),
                "owner_username": self.owner_username,
                "owner_id": self.owner_id,
            },
            "conversas": [self._thread_to_dict(t) for t in self.threads],
        }

        if include_stats:
            stats = ChatStatistics(self.threads, self.owner_username, self.owner_id,
                                   base_dir=self.base_dir)
            data["estatisticas"] = stats.generate_all()

        if self.profile_media and self.profile_media.generic_categories:
            data["outras_categorias"] = [
                {
                    "categoria_nome": cat.category_name,
                    "categoria_id": cat.category_id,
                    "registros": [
                        {"entradas": rec.entries} for rec in cat.records
                    ]
                }
                for cat in self.profile_media.generic_categories
            ]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        logger.info("JSON exportado: %s", output_path)
        return output_path

    def _thread_to_dict(self, thread: Thread) -> dict:
        """Converte Thread para dicionário"""
        participants = [
            {"nome": p[0], "plataforma": p[1], "id": p[2]}
            for p in thread.participants
        ]

        messages = [self._message_to_dict(m) for m in thread.messages]

        dates = [m.sent for m in thread.messages if m.sent]
        first_date = min(dates).strftime("%Y-%m-%d %H:%M:%S") if dates else None
        last_date = max(dates).strftime("%Y-%m-%d %H:%M:%S") if dates else None

        return {
            "thread_id": thread.thread_id,
            "nome": thread.thread_name,
            "participantes": participants,
            "ai_enabled": thread.ai_enabled,
            "read_receipts": thread.read_receipts,
            "total_mensagens": len(thread.messages),
            "primeira_mensagem": first_date,
            "ultima_mensagem": last_date,
            "mensagens": messages,
        }

    @staticmethod
    def _message_to_dict(msg: Message) -> dict:
        """Converte Message para dicionário"""
        attachments = [
            {
                "filename": att.filename,
                "tipo": att.file_type,
                "caminho": att.local_path,
            }
            for att in msg.attachments
        ]

        result = {
            "autor": msg.author,
            "autor_id": msg.author_id,
            "plataforma": msg.platform,
            "enviado": msg.sent.strftime("%Y-%m-%d %H:%M:%S") if msg.sent else None,
            "corpo": msg.body,
        }

        # Campos opcionais - só incluir se relevantes
        if msg.disappearing:
            result["temporaria"] = True
            result["duracao_temporaria"] = msg.disappearing_duration
        if msg.attachments:
            result["anexos"] = attachments
        if msg.share_url:
            result["link_compartilhado"] = msg.share_url
            result["texto_compartilhado"] = msg.share_text
        if msg.is_call:
            result["chamada"] = {
                "tipo": msg.call_type,
                "duracao": msg.call_duration,
                "perdida": msg.call_missed,
            }
        if msg.removed_by_sender:
            result["removida"] = True
        if msg.source_file:
            result["arquivo_origem"] = msg.source_file

        return result


class CSVExporter:
    """Exporta conversas para formato CSV"""

    def __init__(self, threads: List[Thread], owner_username: str = "", owner_id: str = "",
                 base_dir=None, profile_media=None):
        self.threads = threads
        self.owner_username = owner_username
        self.owner_id = owner_id
        self.base_dir = base_dir
        self.profile_media = profile_media

    def export(self, output_path: Path) -> Path:
        """Exporta todas as mensagens para CSV"""
        logger.info("Exportando para CSV: %s", output_path)

        # Verificar se o diretório de destino é gravável
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "conversa_id", "conversa_nome", "autor", "autor_id", "plataforma",
            "data_hora", "corpo", "temporaria", "duracao_temporaria",
            "anexos", "tipos_anexo", "link_compartilhado", "texto_compartilhado",
            "eh_chamada", "tipo_chamada", "duracao_chamada", "chamada_perdida",
            "removida_pelo_remetente", "arquivo_origem"
        ]

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()

            for thread in self.threads:
                thread_name = thread.thread_name or ", ".join(
                    [p[0] for p in thread.participants[:3]]
                )
                for msg in thread.messages:
                    row = self._message_to_row(thread.thread_id, thread_name, msg)
                    writer.writerow(row)

        if self.profile_media and self.profile_media.generic_categories:
            for cat in self.profile_media.generic_categories:
                cat_filename = output_path.stem + f"_cat_{cat.category_id}.csv"
                cat_path = output_path.with_name(cat_filename)
                
                fieldnames_cat = []
                for rec in cat.records:
                    for entry in rec.entries:
                        for k in entry.keys():
                            if k not in fieldnames_cat:
                                fieldnames_cat.append(k)
                if fieldnames_cat:
                    with open(cat_path, 'w', encoding='utf-8-sig', newline='') as f_cat:
                        cat_writer = csv.DictWriter(f_cat, fieldnames=fieldnames_cat, extrasaction='ignore')
                        cat_writer.writeheader()
                        for rec in cat.records:
                            for entry in rec.entries:
                                cat_writer.writerow(entry)
                    logger.info("CSV adicional para categoria exportado: %s", cat_path)

        logger.info("CSV exportado: %s", output_path)
        return output_path

    @staticmethod
    def _message_to_row(thread_id: str, thread_name: str, msg: Message) -> dict:
        """Converte Message para linha CSV"""
        attachments = "; ".join(att.filename for att in msg.attachments) if msg.attachments else ""
        att_types = "; ".join(att.file_type for att in msg.attachments) if msg.attachments else ""

        row = {
            "conversa_id": thread_id,
            "conversa_nome": thread_name,
            "autor": msg.author,
            "autor_id": msg.author_id,
            "plataforma": msg.platform,
            "data_hora": msg.sent.strftime("%Y-%m-%d %H:%M:%S") if msg.sent else "",
            "corpo": msg.body,
            "temporaria": "Sim" if msg.disappearing else "Não",
            "duracao_temporaria": msg.disappearing_duration,
            "anexos": attachments,
            "tipos_anexo": att_types,
            "link_compartilhado": msg.share_url or "",
            "texto_compartilhado": msg.share_text or "",
            "eh_chamada": "Sim" if msg.is_call else "Não",
            "tipo_chamada": msg.call_type,
            "duracao_chamada": msg.call_duration,
            "chamada_perdida": "Sim" if msg.call_missed else "Não",
            "removida_pelo_remetente": "Sim" if msg.removed_by_sender else "Não",
            "arquivo_origem": msg.source_file,
        }
        # Sanitizar valores string contra CSV injection
        return {k: _sanitize_csv_value(v) for k, v in row.items()}

    def export_stats(self, output_path: Path) -> Path:
        """Exporta estatísticas para CSV separado"""
        logger.info("Exportando estatísticas para CSV: %s", output_path)

        stats = ChatStatistics(self.threads, self.owner_username, self.owner_id,
                               base_dir=self.base_dir)
        all_stats = stats.generate_all()

        # Exportar resumo por participante
        participants = all_stats["por_participante"]
        if participants:
            fieldnames = list(participants[0].keys())
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for p in participants:
                    writer.writerow(p)

        logger.info("Estatísticas CSV exportadas: %s", output_path)
        return output_path
