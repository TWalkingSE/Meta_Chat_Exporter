"""
Meta Platforms Chat Exporter - Estatísticas e Analytics
Gera estatísticas detalhadas sobre as conversas exportadas
"""

import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from langdetect import DetectorFactory, detect_langs
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    detect_langs = None
    LANGDETECT_AVAILABLE = False

    class LangDetectException(Exception):
        """Fallback local quando langdetect não está instalado."""

from models import Thread, Message

logger = logging.getLogger(__name__)


class ChatStatistics:
    """Gera estatísticas detalhadas sobre conversas"""

    _LANG_KEYWORDS = {
        "Português": {"que", "não", "para", "com", "uma", "isso", "mas", "foi", "tem", "são",
                       "está", "como", "mais", "por", "dos", "das", "ela", "ele", "meu", "sua",
                       "sim", "também", "bem", "aqui", "agora", "hoje", "muito", "bom", "tudo",
                       "quando", "onde", "quem", "pode", "fazer", "acho", "vc", "kkk", "tbm", "pra"},
        "English": {"the", "and", "you", "that", "was", "for", "are", "with", "his", "they",
                    "have", "this", "from", "but", "not", "what", "can", "had", "her", "she",
                    "been", "would", "there", "their", "will", "when", "who", "more", "just",
                    "about", "know", "like", "your", "how", "think", "yeah", "okay", "right"},
        "Español": {"que", "por", "para", "con", "una", "pero", "más", "como", "fue", "sus",
                    "ella", "está", "hay", "esto", "también", "bien", "aquí", "ahora", "hoy",
                    "mucho", "todo", "cuando", "donde", "quién", "puede", "hacer", "creo", "bueno"},
    }
    _LANG_CODE_MAP = {
        "pt": "Português",
        "pt-br": "Português",
        "en": "English",
        "es": "Español",
    }
    _LANG_MIN_CHARS = 20
    _LANG_MESSAGE_LIMIT = 300
    _LANG_CHUNK_TARGET = 1500
    _LANG_MAX_CHUNKS = 20

    def __init__(self, threads: List[Thread], owner_username: str = "", owner_id: str = "",
                 base_dir: Optional[Path] = None):
        self.threads = threads
        self.owner_username = owner_username
        self.owner_id = owner_id
        self.base_dir = base_dir

    def generate_all(self) -> Dict[str, Any]:
        """Gera todas as estatísticas"""
        logger.info("Gerando estatísticas...")
        all_messages = []
        for t in self.threads:
            all_messages.extend(t.messages)

        stats = {
            "resumo": self._resumo_geral(all_messages),
            "por_participante": self._stats_por_participante(all_messages),
            "por_conversa": self._stats_por_conversa(),
            "temporal": self._stats_temporal(all_messages),
            "midias": self._stats_midias(all_messages),
            "chamadas": self._stats_chamadas(all_messages),
            "palavras": self._stats_palavras(all_messages),
            "horarios": self._stats_horarios(all_messages),
            "top_conversas": self._top_conversas(),
            "tempo_resposta": self._stats_tempo_resposta(),
            "heatmap": self._stats_heatmap(all_messages),
            "reacoes": self._stats_reacoes(all_messages),
            "emojis": self._stats_emojis(all_messages),
            "integridade_anexos": self._stats_integridade_anexos(all_messages),
            "gaps": self._stats_gaps(),
            "grafo": self._stats_grafo(),
            "tamanho_msgs": self._stats_tamanho_mensagens(all_messages),
            "comparacao_periodos": self._stats_comparacao_periodos(all_messages),
            "idiomas": self._stats_idiomas(all_messages),
            "timeline": self._stats_timeline(),
        }
        logger.info("Estatísticas geradas com sucesso!")
        return stats

    def _resumo_geral(self, messages: List[Message]) -> Dict[str, Any]:
        """Resumo geral de todas as conversas"""
        total_msgs = len(messages)
        total_threads = len(self.threads)

        dates = [m.sent for m in messages if m.sent]
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None

        total_attachments = sum(len(m.attachments) for m in messages)
        total_calls = sum(1 for m in messages if m.is_call)
        total_disappearing = sum(1 for m in messages if m.disappearing)
        total_removed = sum(1 for m in messages if m.removed_by_sender)
        total_shares = sum(1 for m in messages if m.share_url)
        total_reactions = sum(1 for m in messages if m.is_reaction)
        total_payments = sum(1 for m in messages if m.has_payment)
        total_subscriptions = sum(1 for m in messages if m.subscription_event)

        # Participantes únicos
        participants = set()
        for t in self.threads:
            for p in t.participants:
                participants.add(p[0])

        # Classificação DM vs Grupo
        total_dms = sum(1 for t in self.threads if len(t.participants) <= 2)
        total_grupos = sum(1 for t in self.threads if len(t.participants) > 2)
        msgs_dms = sum(
            len(t.messages) for t in self.threads if len(t.participants) <= 2
        )
        msgs_grupos = sum(
            len(t.messages) for t in self.threads if len(t.participants) > 2
        )

        # Média de mensagens por dia
        if first_date and last_date:
            days = max((last_date - first_date).days, 1)
            msgs_per_day = total_msgs / days
        else:
            days = 0
            msgs_per_day = 0

        return {
            "total_mensagens": total_msgs,
            "total_conversas": total_threads,
            "total_participantes": len(participants),
            "total_anexos": total_attachments,
            "total_chamadas": total_calls,
            "total_temporarias": total_disappearing,
            "total_removidas": total_removed,
            "total_compartilhamentos": total_shares,
            "primeira_mensagem": first_date.strftime("%d/%m/%Y %H:%M") if first_date else "N/A",
            "ultima_mensagem": last_date.strftime("%d/%m/%Y %H:%M") if last_date else "N/A",
            "periodo_dias": days,
            "media_mensagens_dia": round(msgs_per_day, 1),
            "total_reacoes": total_reactions,
            "total_pagamentos": total_payments,
            "total_eventos_grupo": total_subscriptions,
            "total_dms": total_dms,
            "total_grupos": total_grupos,
            "msgs_dms": msgs_dms,
            "msgs_grupos": msgs_grupos,
        }

    def _stats_por_participante(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Estatísticas por participante"""
        participant_stats = defaultdict(lambda: {
            "mensagens": 0,
            "caracteres": 0,
            "anexos": 0,
            "chamadas": 0,
            "audios": 0,
            "fotos": 0,
            "videos": 0,
            "links": 0,
            "reacoes": 0,
        })

        for msg in messages:
            name = msg.author
            participant_stats[name]["mensagens"] += 1
            participant_stats[name]["caracteres"] += len(msg.body or "")
            participant_stats[name]["anexos"] += len(msg.attachments)
            if msg.is_call:
                participant_stats[name]["chamadas"] += 1
            if msg.share_url:
                participant_stats[name]["links"] += 1
            if msg.is_reaction:
                participant_stats[name]["reacoes"] += 1
            for att in msg.attachments:
                if "audio" in att.file_type:
                    participant_stats[name]["audios"] += 1
                elif "image" in att.file_type:
                    participant_stats[name]["fotos"] += 1
                elif "video" in att.file_type:
                    participant_stats[name]["videos"] += 1

        result = []
        for name, data in participant_stats.items():
            avg_chars = data["caracteres"] / max(data["mensagens"], 1)
            result.append({
                "nome": name,
                "mensagens": data["mensagens"],
                "caracteres_total": data["caracteres"],
                "media_caracteres": round(avg_chars, 1),
                "anexos": data["anexos"],
                "chamadas": data["chamadas"],
                "audios": data["audios"],
                "fotos": data["fotos"],
                "videos": data["videos"],
                "links": data["links"],
                "reacoes": data["reacoes"],
            })

        result.sort(key=lambda x: x["mensagens"], reverse=True)
        return result

    def _stats_por_conversa(self) -> List[Dict[str, Any]]:
        """Estatísticas por conversa"""
        result = []
        for t in self.threads:
            participants = [p[0] for p in t.participants]
            dates = [m.sent for m in t.messages if m.sent]
            first = min(dates) if dates else None
            last = max(dates) if dates else None

            attachments = sum(len(m.attachments) for m in t.messages)
            calls = sum(1 for m in t.messages if m.is_call)

            name = t.thread_name or ", ".join(participants[:3])
            tipo = "Grupo" if len(t.participants) > 2 else "DM"

            result.append({
                "nome": name,
                "thread_id": t.thread_id,
                "tipo": tipo,
                "participantes": len(t.participants),
                "mensagens": len(t.messages),
                "anexos": attachments,
                "chamadas": calls,
                "primeira_msg": first.strftime("%d/%m/%Y") if first else "N/A",
                "ultima_msg": last.strftime("%d/%m/%Y") if last else "N/A",
            })

        result.sort(key=lambda x: x["mensagens"], reverse=True)
        return result

    def _stats_temporal(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas temporais - mensagens por mês, semana, dia da semana"""
        por_mes = Counter()
        por_dia_semana = Counter()
        por_ano = Counter()

        dias_semana_nomes = [
            "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"
        ]

        for msg in messages:
            if not msg.sent:
                continue
            por_mes[msg.sent.strftime("%Y-%m")] += 1
            por_dia_semana[msg.sent.weekday()] += 1
            por_ano[msg.sent.year] += 1

        # Ordenar meses cronologicamente
        meses_ordenados = sorted(por_mes.items())

        # Dia da semana mais ativo
        dia_mais_ativo = max(por_dia_semana, key=por_dia_semana.get) if por_dia_semana else 0

        return {
            "por_mes": [{"mes": k, "total": v} for k, v in meses_ordenados],
            "por_dia_semana": [
                {"dia": dias_semana_nomes[i], "total": por_dia_semana.get(i, 0)}
                for i in range(7)
            ],
            "por_ano": [{"ano": k, "total": v} for k, v in sorted(por_ano.items())],
            "dia_mais_ativo": dias_semana_nomes[dia_mais_ativo],
        }

    def _stats_midias(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas de mídias"""
        fotos = 0
        videos = 0
        audios = 0
        outros = 0

        for msg in messages:
            for att in msg.attachments:
                if "image" in att.file_type:
                    fotos += 1
                elif "video" in att.file_type:
                    videos += 1
                elif "audio" in att.file_type:
                    audios += 1
                else:
                    outros += 1

        return {
            "fotos": fotos,
            "videos": videos,
            "audios": audios,
            "outros": outros,
            "total": fotos + videos + audios + outros,
        }

    def _stats_chamadas(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas de chamadas"""
        total = 0
        perdidas = 0
        duracao_total = 0
        tipos = Counter()

        for msg in messages:
            if not msg.is_call:
                continue
            total += 1
            if msg.call_missed:
                perdidas += 1
            duracao_total += msg.call_duration
            if msg.call_type:
                tipos[msg.call_type] += 1

        return {
            "total": total,
            "perdidas": perdidas,
            "atendidas": total - perdidas,
            "duracao_total_segundos": duracao_total,
            "duracao_total_formatada": f"{duracao_total // 3600}h {(duracao_total % 3600) // 60}m",
            "duracao_media_segundos": round(duracao_total / max(total - perdidas, 1)),
            "por_tipo": dict(tipos),
        }

    def _stats_palavras(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas de palavras mais usadas"""
        # Stop words em português
        stop_words = {
            "a", "e", "o", "de", "da", "do", "em", "que", "é", "um", "uma",
            "para", "com", "não", "no", "na", "os", "as", "se", "por", "mais",
            "eu", "mas", "me", "ele", "ela", "te", "isso", "isso", "esse",
            "essa", "este", "esta", "foi", "ser", "tem", "já", "muito", "como",
            "ao", "aos", "das", "dos", "ou", "sua", "seu", "meu", "minha",
            "nao", "ta", "tá", "vc", "voce", "pra", "pro", "só", "so", "sim",
            "aqui", "aí", "ai", "lá", "la", "né", "ne", "eh", "ah", "oh",
            "ok", "vou", "vai", "ter", "tudo", "bem", "dia", "bom", "boa",
            "the", "to", "and", "of", "in", "is", "it", "you", "that", "was",
            "for", "on", "are", "with", "this", "have", "from",
        }

        word_counter = Counter()
        total_words = 0

        for msg in messages:
            if not msg.body or msg.is_call or msg.removed_by_sender:
                continue
            words = msg.body.lower().split()
            for word in words:
                # Limpar pontuação
                clean = word.strip(".,!?;:()[]{}\"'…-_")
                if len(clean) >= 2 and clean not in stop_words:
                    word_counter[clean] += 1
                total_words += 1

        top_50 = word_counter.most_common(50)

        return {
            "total_palavras": total_words,
            "palavras_unicas": len(word_counter),
            "top_50": [{"palavra": w, "contagem": c} for w, c in top_50],
        }

    def _stats_horarios(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas por horário do dia"""
        por_hora = Counter()

        for msg in messages:
            if msg.sent:
                por_hora[msg.sent.hour] += 1

        hora_mais_ativa = max(por_hora, key=por_hora.get) if por_hora else 0

        # Classificação por período
        madrugada = sum(por_hora.get(h, 0) for h in range(0, 6))
        manha = sum(por_hora.get(h, 0) for h in range(6, 12))
        tarde = sum(por_hora.get(h, 0) for h in range(12, 18))
        noite = sum(por_hora.get(h, 0) for h in range(18, 24))

        return {
            "por_hora": [{"hora": f"{h:02d}:00", "total": por_hora.get(h, 0)} for h in range(24)],
            "hora_mais_ativa": f"{hora_mais_ativa:02d}:00",
            "periodos": {
                "madrugada": madrugada,
                "manha": manha,
                "tarde": tarde,
                "noite": noite,
            },
        }

    def _top_conversas(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Top conversas por número de mensagens"""
        convs = []
        for t in self.threads:
            participants = [p[0] for p in t.participants]
            name = t.thread_name or ", ".join(participants[:3])
            convs.append({
                "nome": name,
                "mensagens": len(t.messages),
                "participantes": len(t.participants),
            })

        convs.sort(key=lambda x: x["mensagens"], reverse=True)
        return convs[:limit]

    def _stats_tempo_resposta(self) -> List[Dict[str, Any]]:
        """Análise de tempo de resposta em conversas diretas (DMs)"""
        response_times = defaultdict(list)

        for thread in self.threads:
            if len(thread.participants) != 2:
                continue

            msgs = [m for m in thread.messages if m.sent and not m.is_call and not m.is_reaction]
            if len(msgs) < 2:
                continue

            msgs.sort(key=lambda m: m.sent)

            for i in range(1, len(msgs)):
                prev = msgs[i - 1]
                curr = msgs[i]

                if prev.author != curr.author:
                    delta = (curr.sent - prev.sent).total_seconds()
                    if 0 < delta <= 86400:  # Max 24h
                        response_times[curr.author].append(delta)

        result = []
        for author, times in response_times.items():
            if len(times) >= 3:
                avg = sum(times) / len(times)
                sorted_times = sorted(times)
                median = sorted_times[len(times) // 2]
                result.append({
                    "nome": author,
                    "media_segundos": round(avg),
                    "mediana_segundos": round(median),
                    "media_formatada": self._format_duration(avg),
                    "mediana_formatada": self._format_duration(median),
                    "total_respostas": len(times),
                    "mais_rapida": self._format_duration(min(times)),
                    "mais_lenta": self._format_duration(max(times)),
                })

        result.sort(key=lambda x: x["media_segundos"])
        return result

    def _format_duration(self, seconds: float) -> str:
        """Formata duração em formato legível"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}min{s:02d}s"
        else:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            return f"{h}h{m:02d}min"

    def _stats_heatmap(self, messages: List[Message]) -> List[List[int]]:
        """Gera matriz dia×hora para heatmap de atividade"""
        matrix = [[0] * 24 for _ in range(7)]

        for msg in messages:
            if msg.sent:
                matrix[msg.sent.weekday()][msg.sent.hour] += 1

        return matrix

    def _stats_reacoes(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas de reações (curtidas e reações a mensagens)"""
        total = sum(1 for m in messages if m.is_reaction)
        by_author = Counter()

        for msg in messages:
            if msg.is_reaction:
                by_author[msg.author] += 1

        return {
            "total": total,
            "por_autor": [{"nome": n, "total": c} for n, c in by_author.most_common(10)],
        }

    # Regex Unicode para emojis (cobre Emoji_Presentation + Emoji_Modifier + Regional Indicators etc.)
    _RE_EMOJI = re.compile(
        "[" 
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # símbolos e pictogramas
        "\U0001F680-\U0001F6FF"  # transporte e mapas
        "\U0001F1E0-\U0001F1FF"  # bandeiras
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed chars
        "\U0001F900-\U0001F9FF"  # suplementares
        "\U0001FA00-\U0001FA6F"  # chess, etc
        "\U0001FA70-\U0001FAFF"  # extras
        "\U00002600-\U000026FF"  # misc symbols
        "\U0000FE00-\U0000FE0F"  # variation selectors
        "\U0000200D"             # ZWJ
        "\U00002B50-\U00002B55"  # estrelas
        "\U0000231A-\U0000231B"  # watch/hourglass
        "\U00002934-\U00002935"  # setas
        "\U000025AA-\U000025AB"  # quadrados
        "\U000025FB-\U000025FE"  # quadrados
        "\U00002764"             # coração
        "]+", flags=re.UNICODE
    )

    def _stats_emojis(self, messages: List[Message]) -> Dict[str, Any]:
        """Estatísticas de emojis usados nas mensagens"""
        emoji_counter = Counter()
        emoji_by_author = defaultdict(Counter)
        total_msgs_with_emoji = 0

        for msg in messages:
            if not msg.body or msg.is_call or msg.removed_by_sender:
                continue
            emojis_found = self._RE_EMOJI.findall(msg.body)
            if emojis_found:
                total_msgs_with_emoji += 1
                for emoji in emojis_found:
                    # Cada char individual do match (pode ter ZWJ sequences)
                    for ch in emoji:
                        if ch not in ('\ufe0f', '\u200d', '\ufe0e'):  # skip modifiers
                            emoji_counter[ch] += 1
                            emoji_by_author[msg.author][ch] += 1

        top_30 = emoji_counter.most_common(30)
        top_by_author = []
        for author, counter in sorted(emoji_by_author.items(), key=lambda x: sum(x[1].values()), reverse=True)[:10]:
            top_by_author.append({
                "nome": author,
                "total": sum(counter.values()),
                "top_3": [e for e, _ in counter.most_common(3)],
            })

        return {
            "total_emojis": sum(emoji_counter.values()),
            "emojis_unicos": len(emoji_counter),
            "msgs_com_emoji": total_msgs_with_emoji,
            "top_30": [{"emoji": e, "contagem": c} for e, c in top_30],
            "por_autor": top_by_author,
        }

    def _stats_integridade_anexos(self, messages: List[Message]) -> Dict[str, Any]:
        """Verifica integridade dos anexos (se os arquivos existem no disco)"""
        total = 0
        encontrados = 0
        faltando = 0
        faltando_lista = []

        for msg in messages:
            for att in msg.attachments:
                if not att.local_path:
                    continue
                total += 1

                # Tentar resolver caminho relativo a partir do base_dir de cada thread
                found = False
                check_path = Path(att.local_path)
                if check_path.is_absolute() and check_path.exists():
                    found = True
                elif self.base_dir:
                    full = self.base_dir / att.local_path
                    if full.exists():
                        found = True

                # Tentar a partir de base_dir dos threads
                if not found:
                    for t in self.threads:
                        if t.base_dir:
                            full = t.base_dir / att.local_path
                            if full.exists():
                                found = True
                                break

                if found:
                    encontrados += 1
                else:
                    faltando += 1
                    if len(faltando_lista) < 20:
                        faltando_lista.append({
                            "arquivo": att.filename,
                            "caminho": att.local_path,
                            "autor": msg.author,
                            "data": msg.sent.strftime("%d/%m/%Y") if msg.sent else "N/A",
                        })

        return {
            "total": total,
            "encontrados": encontrados,
            "faltando": faltando,
            "percentual_ok": round(encontrados / max(total, 1) * 100, 1),
            "faltando_lista": faltando_lista,
        }

    def _stats_gaps(self, min_days: int = 30) -> Dict[str, Any]:
        """Detecta períodos de inatividade (gaps) maiores que min_days em cada conversa"""
        all_gaps = []

        for thread in self.threads:
            dates = sorted([m.sent for m in thread.messages if m.sent])
            if len(dates) < 2:
                continue

            for i in range(1, len(dates)):
                delta = dates[i] - dates[i - 1]
                if delta.days >= min_days:
                    all_gaps.append({
                        "conversa": thread.thread_name or "Sem nome",
                        "de": dates[i - 1].strftime("%d/%m/%Y"),
                        "ate": dates[i].strftime("%d/%m/%Y"),
                        "dias": delta.days,
                    })

        # Ordenar por duração (maior primeiro)
        all_gaps.sort(key=lambda g: g["dias"], reverse=True)

        # Estatísticas gerais
        total_gaps = len(all_gaps)
        conversas_com_gaps = len(set(g["conversa"] for g in all_gaps))
        maior_gap = all_gaps[0] if all_gaps else None

        return {
            "total_gaps": total_gaps,
            "conversas_com_gaps": conversas_com_gaps,
            "maior_gap": maior_gap,
            "min_dias": min_days,
            "gaps": all_gaps[:50],  # Limitar a 50 maiores
        }

    def _stats_grafo(self, max_nodes: int = 30) -> Dict[str, Any]:
        """Gera dados para grafo de relacionamentos entre participantes"""
        import math
        import html as html_mod

        # Contar mensagens entre pares de participantes (co-ocorrência em threads)
        pair_counts = Counter()
        node_counts = Counter()

        for thread in self.threads:
            names = sorted(set(p[0] for p in thread.participants))
            msg_count = len(thread.messages)
            if msg_count == 0:
                continue

            for name in names:
                node_counts[name] += msg_count

            # Gerar pares (co-ocorrência = compartilham a mesma conversa)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pair_counts[(names[i], names[j])] += msg_count

        if not node_counts:
            return {"svg": "", "total_nos": 0, "total_conexoes": 0}

        # Limitar aos top N participantes por mensagens
        top_nodes = [n for n, _ in node_counts.most_common(max_nodes)]
        top_set = set(top_nodes)
        n = len(top_nodes)

        # Filtrar pares com apenas nós do top
        filtered_pairs = {
            k: v for k, v in pair_counts.items()
            if k[0] in top_set and k[1] in top_set
        }

        if not filtered_pairs:
            return {"svg": "", "total_nos": n, "total_conexoes": 0}

        # Gerar posições em círculo
        width, height = 800, 600
        cx, cy = width / 2, height / 2
        radius = min(cx, cy) - 80
        positions = {}
        for i, name in enumerate(top_nodes):
            angle = 2 * math.pi * i / n - math.pi / 2
            positions[name] = (
                cx + radius * math.cos(angle),
                cy + radius * math.sin(angle)
            )

        # Normalizar espessura das linhas
        max_weight = max(filtered_pairs.values()) if filtered_pairs else 1
        min_weight = min(filtered_pairs.values()) if filtered_pairs else 1

        # Gerar SVG
        svg_lines = []
        for (a, b), weight in filtered_pairs.items():
            x1, y1 = positions[a]
            x2, y2 = positions[b]
            # Espessura: 0.5 a 4px
            if max_weight > min_weight:
                thickness = 0.5 + 3.5 * (weight - min_weight) / (max_weight - min_weight)
            else:
                thickness = 2
            opacity = 0.15 + 0.5 * (weight - min_weight) / max(max_weight - min_weight, 1)
            svg_lines.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#6366f1" stroke-width="{thickness:.1f}" opacity="{opacity:.2f}"/>'
            )

        # Normalizar tamanho dos nós
        max_node = max(node_counts[n] for n in top_nodes)
        min_node = min(node_counts[n] for n in top_nodes)

        svg_nodes = []
        for name in top_nodes:
            x, y = positions[name]
            count = node_counts[name]
            if max_node > min_node:
                r = 6 + 14 * (count - min_node) / (max_node - min_node)
            else:
                r = 10
            # Truncar nome
            display = name[:12] + "…" if len(name) > 12 else name
            display = html_mod.escape(display)
            svg_nodes.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#6366f1" stroke="#fff" stroke-width="1.5"/>'
                f'<text x="{x:.1f}" y="{y + r + 14:.1f}" text-anchor="middle" '
                f'fill="#444" font-size="10" font-family="sans-serif">{display}</text>'
            )

        svg = (
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:{width}px;height:auto;background:#fafafa;border-radius:12px;">'
            + "\n".join(svg_lines) + "\n" + "\n".join(svg_nodes) +
            '</svg>'
        )

        return {
            "svg": svg,
            "total_nos": n,
            "total_conexoes": len(filtered_pairs),
        }

    def _stats_tamanho_mensagens(self, messages: List[Message]) -> Dict[str, Any]:
        """Distribuição de tamanho de mensagens (histograma por faixas de caracteres)"""
        faixas = [
            (0, 10, "0-10"),
            (11, 50, "11-50"),
            (51, 150, "51-150"),
            (151, 500, "151-500"),
            (501, 1000, "501-1000"),
            (1001, float('inf'), "1000+"),
        ]

        # Distribuição geral
        dist_geral = Counter()
        # Por participante (top 10)
        dist_por_autor = defaultdict(Counter)
        total_chars = 0
        total_msgs_com_texto = 0

        for msg in messages:
            if not msg.body:
                continue
            length = len(msg.body)
            total_chars += length
            total_msgs_com_texto += 1

            for lo, hi, label in faixas:
                if lo <= length <= hi:
                    dist_geral[label] += 1
                    dist_por_autor[msg.author][label] += 1
                    break

        # Top autores por volume
        author_totals = Counter()
        for author, counts in dist_por_autor.items():
            author_totals[author] = sum(counts.values())
        top_authors = [a for a, _ in author_totals.most_common(8)]

        media_chars = round(total_chars / max(total_msgs_com_texto, 1), 1)

        return {
            "distribuicao": {label: dist_geral.get(label, 0) for _, _, label in faixas},
            "faixas": [label for _, _, label in faixas],
            "por_autor": {a: {label: dist_por_autor[a].get(label, 0) for _, _, label in faixas} for a in top_authors},
            "media_chars": media_chars,
            "total_msgs_com_texto": total_msgs_com_texto,
        }

    def _stats_comparacao_periodos(self, messages: List[Message]) -> Dict[str, Any]:
        """Compara métricas entre primeira e segunda metade do período total"""
        dated = [m for m in messages if m.sent]
        if len(dated) < 2:
            return {"ativo": False}

        dates = sorted(m.sent for m in dated)
        mid_date = dates[len(dates) // 2]
        first_date = dates[0]
        last_date = dates[-1]

        p1 = [m for m in dated if m.sent < mid_date]
        p2 = [m for m in dated if m.sent >= mid_date]

        def _metrics(msgs):
            total = len(msgs)
            anexos = sum(len(m.attachments) for m in msgs)
            chamadas = sum(1 for m in msgs if m.is_call)
            chars = sum(len(m.body) for m in msgs if m.body)
            autores = len(set(m.author for m in msgs))
            media_len = round(chars / max(total, 1), 1)
            return {
                "msgs": total,
                "anexos": anexos,
                "chamadas": chamadas,
                "chars": chars,
                "autores": autores,
                "media_len": media_len
            }

        m1 = _metrics(p1)
        m2 = _metrics(p2)

        def _variacao(v1, v2):
            if v1 == 0:
                return "+100%" if v2 > 0 else "0%"
            pct = round((v2 - v1) / v1 * 100, 1)
            return f"{pct:+.1f}%"

        return {
            "ativo": True,
            "p1_de": first_date.strftime("%d/%m/%Y"),
            "p1_ate": (mid_date - timedelta(days=1)).strftime("%d/%m/%Y"),
            "p2_de": mid_date.strftime("%d/%m/%Y"),
            "p2_ate": last_date.strftime("%d/%m/%Y"),
            "p1": m1,
            "p2": m2,
            "variacoes": {
                "msgs": _variacao(m1["msgs"], m2["msgs"]),
                "anexos": _variacao(m1["anexos"], m2["anexos"]),
                "chamadas": _variacao(m1["chamadas"], m2["chamadas"]),
                "autores": _variacao(m1["autores"], m2["autores"]),
                "media_len": _variacao(m1["media_len"], m2["media_len"]),
            }
        }

    def _normalize_language_text(self, text: str) -> str:
        """Normaliza texto para detecção de idioma."""
        normalized = re.sub(r'\s+', ' ', (text or '').strip())
        return normalized[:self._LANG_CHUNK_TARGET]

    def _build_language_chunks(self, messages: List[Message]) -> List[str]:
        """Agrupa mensagens em chunks maiores para melhorar a acurácia do detector."""
        chunks = []
        current_parts = []
        current_size = 0
        processed = 0

        for msg in messages:
            if processed >= self._LANG_MESSAGE_LIMIT or len(chunks) >= self._LANG_MAX_CHUNKS:
                break
            if not msg.body:
                continue

            text = self._normalize_language_text(msg.body)
            if len(text) < self._LANG_MIN_CHARS:
                continue

            processed += 1
            if current_parts and current_size + len(text) + 1 > self._LANG_CHUNK_TARGET:
                chunks.append(' '.join(current_parts))
                current_parts = []
                current_size = 0
                if len(chunks) >= self._LANG_MAX_CHUNKS:
                    break

            current_parts.append(text)
            current_size += len(text) + 1

        if current_parts and len(chunks) < self._LANG_MAX_CHUNKS:
            chunks.append(' '.join(current_parts))

        return chunks

    def _stats_idiomas_keywords(self, messages: List[Message]) -> Dict[str, Any]:
        """Fallback simples baseado em palavras-chave quando langdetect não está disponível."""
        word_counter = Counter()

        for msg in messages:
            if not msg.body or len(msg.body) < 10:
                continue
            words = set(msg.body.lower().split())
            for word in words:
                if len(word) >= 2:
                    word_counter[word] += 1

        lang_scores = {}
        for lang, keywords in self._LANG_KEYWORDS.items():
            score = sum(word_counter.get(keyword, 0) for keyword in keywords)
            lang_scores[lang] = score

        total_score = sum(lang_scores.values())
        if total_score == 0:
            return {
                "principal": "Indeterminado",
                "percentuais": {},
                "scores": {},
                "metodo": "keywords",
            }

        percentuais = {
            lang: round(score / total_score * 100, 1)
            for lang, score in sorted(lang_scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        }
        principal = max(lang_scores, key=lang_scores.get)

        return {
            "principal": principal,
            "percentuais": percentuais,
            "scores": lang_scores,
            "metodo": "keywords",
        }

    def _stats_idiomas_langdetect(self, messages: List[Message]) -> Optional[Dict[str, Any]]:
        """Tenta detectar idioma com langdetect, se disponível."""
        if not LANGDETECT_AVAILABLE or detect_langs is None:
            return None

        chunks = self._build_language_chunks(messages)
        if not chunks:
            return None

        lang_scores = defaultdict(float)
        analyzed_chunks = 0

        for chunk in chunks:
            try:
                detections = detect_langs(chunk)
            except LangDetectException:
                continue

            for detection in detections:
                lang_code = detection.lang.lower()
                lang_name = self._LANG_CODE_MAP.get(lang_code)
                if lang_name:
                    lang_scores[lang_name] += detection.prob
            analyzed_chunks += 1

        total_score = sum(lang_scores.values())
        if analyzed_chunks == 0 or total_score == 0:
            return None

        percentuais = {
            lang: round(score / total_score * 100, 1)
            for lang, score in sorted(lang_scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        }
        principal = max(lang_scores, key=lang_scores.get)

        return {
            "principal": principal,
            "percentuais": percentuais,
            "scores": {lang: round(score, 4) for lang, score in lang_scores.items()},
            "metodo": "langdetect",
            "amostras_analisadas": analyzed_chunks,
        }

    def _stats_idiomas(self, messages: List[Message]) -> Dict[str, Any]:
        """Detecta idiomas predominantes, usando langdetect quando disponível."""
        detected = self._stats_idiomas_langdetect(messages)
        if detected:
            return detected
        return self._stats_idiomas_keywords(messages)

    def _stats_timeline(self) -> List[Dict[str, Any]]:
        """Gera dados de timeline para cada conversa (início, fim, volume)"""
        timeline = []
        for t in self.threads:
            dates = [m.sent for m in t.messages if m.sent]
            if not dates:
                continue
            first = min(dates)
            last = max(dates)
            name = t.thread_name or (t.participants[0].username if t.participants else t.thread_id)
            timeline.append({
                "name": name,
                "start": first,
                "end": last,
                "count": len(t.messages),
            })
        timeline.sort(key=lambda x: x["start"])
        return timeline

    def generate_html_report(self) -> str:
        """Gera um relatório HTML completo com gráficos CSS"""
        stats = self.generate_all()
        resumo = stats["resumo"]
        participantes = stats["por_participante"]
        temporal = stats["temporal"]
        midias = stats["midias"]
        chamadas = stats["chamadas"]
        palavras = stats["palavras"]
        horarios = stats["horarios"]
        top = stats["top_conversas"]
        tempo_resposta = stats["tempo_resposta"]
        heatmap = stats["heatmap"]
        reacoes = stats["reacoes"]
        emojis = stats["emojis"]
        integridade = stats["integridade_anexos"]
        gaps = stats["gaps"]
        grafo = stats["grafo"]
        tamanho_msgs = stats["tamanho_msgs"]
        comparacao = stats["comparacao_periodos"]
        idiomas = stats["idiomas"]
        timeline = stats["timeline"]

        # Cards de resumo
        cards_html = f'''
        <div class="stats-cards">
            <div class="stat-card">
                <div class="stat-number">{resumo["total_mensagens"]:,}</div>
                <div class="stat-label">Mensagens</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["total_conversas"]}</div>
                <div class="stat-label">Conversas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["total_participantes"]}</div>
                <div class="stat-label">Participantes</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["total_anexos"]}</div>
                <div class="stat-label">Anexos</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["media_mensagens_dia"]}</div>
                <div class="stat-label">Msgs/dia</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["periodo_dias"]}</div>
                <div class="stat-label">Dias</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{resumo["total_reacoes"]:,}</div>
                <div class="stat-label">Reações</div>
            </div>
        </div>
        <div class="stats-period">
            {resumo["primeira_mensagem"]} → {resumo["ultima_mensagem"]}
        </div>
        '''

        # Top participantes (barras horizontais)
        max_msgs = participantes[0]["mensagens"] if participantes else 1
        participants_html = ""
        for p in participantes[:15]:
            pct = (p["mensagens"] / max_msgs) * 100
            participants_html += f'''
            <div class="bar-row">
                <div class="bar-label">{p["nome"][:20]}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%"></div>
                </div>
                <div class="bar-value">{p["mensagens"]:,}</div>
            </div>'''

        # Atividade por hora
        max_hour = max((h["total"] for h in horarios["por_hora"]), default=1)
        hours_html = ""
        for h in horarios["por_hora"]:
            pct = (h["total"] / max_hour) * 100 if max_hour > 0 else 0
            hours_html += f'<div class="hour-bar" style="height:{pct}%" title="{h["hora"]}: {h["total"]} msgs"></div>'

        hour_labels = ""
        for i in range(0, 24, 3):
            hour_labels += f'<span>{i:02d}h</span>'

        # Atividade por dia da semana
        max_day = max((d["total"] for d in temporal["por_dia_semana"]), default=1)
        weekdays_html = ""
        for d in temporal["por_dia_semana"]:
            pct = (d["total"] / max_day) * 100 if max_day > 0 else 0
            weekdays_html += f'''
            <div class="weekday-item">
                <div class="weekday-bar-track">
                    <div class="weekday-bar-fill" style="height:{pct}%"></div>
                </div>
                <div class="weekday-label">{d["dia"][:3]}</div>
                <div class="weekday-value">{d["total"]:,}</div>
            </div>'''

        # Top palavras (logarithmic scale + color gradient)
        words_html = ""
        top_words = palavras["top_50"][:40]
        if top_words:
            import math
            max_count = top_words[0]["contagem"] if top_words else 1
            min_count = top_words[-1]["contagem"] if top_words else 1
            log_max = math.log(max_count + 1)
            log_min = math.log(min_count + 1)
            log_range = log_max - log_min if log_max != log_min else 1
            # Color stops: blue(#4a90d9) → purple(#8b5cf6) → red(#e74c3c)
            colors = [
                (74, 144, 217),   # blue
                (139, 92, 246),   # purple
                (231, 76, 60),    # red
            ]
            for i, w in enumerate(top_words):
                t = (math.log(w["contagem"] + 1) - log_min) / log_range
                size = int(13 + t * 25)  # 13px to 38px
                # Interpolate color
                if t < 0.5:
                    ct = t * 2
                    r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ct)
                    g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ct)
                    b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ct)
                else:
                    ct = (t - 0.5) * 2
                    r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * ct)
                    g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * ct)
                    b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * ct)
                color = f'rgb({r},{g},{b})'
                words_html += f'<span class="word-tag" style="font-size:{size}px;color:{color}">{w["palavra"]} <small>({w["contagem"]})</small></span> '

        # Mídias
        midias_html = f'''
        <div class="media-stats">
            <div class="media-stat-item">
                <div class="media-stat-icon">📷</div>
                <div class="media-stat-value">{midias["fotos"]}</div>
                <div class="media-stat-label">Fotos</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">🎬</div>
                <div class="media-stat-value">{midias["videos"]}</div>
                <div class="media-stat-label">Vídeos</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">🎤</div>
                <div class="media-stat-value">{midias["audios"]}</div>
                <div class="media-stat-label">Áudios</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">📎</div>
                <div class="media-stat-value">{midias["outros"]}</div>
                <div class="media-stat-label">Outros</div>
            </div>
        </div>'''

        # Chamadas
        chamadas_html = f'''
        <div class="calls-stats">
            <div class="call-stat">📞 Total: <strong>{chamadas["total"]}</strong></div>
            <div class="call-stat">✅ Atendidas: <strong>{chamadas["atendidas"]}</strong></div>
            <div class="call-stat">📵 Perdidas: <strong>{chamadas["perdidas"]}</strong></div>
            <div class="call-stat">⏱️ Duração total: <strong>{chamadas["duracao_total_formatada"]}</strong></div>
        </div>'''

        # Top conversas
        top_html = ""
        for i, c in enumerate(top):
            top_html += f'''
            <div class="top-conv-item">
                <span class="top-rank">#{i+1}</span>
                <span class="top-name">{c["nome"][:30]}</span>
                <span class="top-msgs">{c["mensagens"]:,} msgs</span>
            </div>'''

        # Atividade mensal (últimos 12 meses ou todos)
        monthly_data = temporal["por_mes"][-24:]  # últimos 24 meses
        max_month = max((m["total"] for m in monthly_data), default=1)
        monthly_html = ""
        for m in monthly_data:
            pct = (m["total"] / max_month) * 100 if max_month > 0 else 0
            monthly_html += f'''
            <div class="month-bar-item">
                <div class="month-bar-track">
                    <div class="month-bar-fill" style="height:{pct}%"></div>
                </div>
                <div class="month-label">{m["mes"][5:]}/{m["mes"][:4]}</div>
            </div>'''

        # Tempo de resposta
        response_time_html = ""
        if tempo_resposta:
            for rt in tempo_resposta[:10]:
                response_time_html += f'''
            <div class="rt-row">
                <span class="rt-name">{rt["nome"][:25]}</span>
                <span class="rt-stat">⏱️ Média: <strong>{rt["media_formatada"]}</strong></span>
                <span class="rt-stat">📊 Mediana: <strong>{rt["mediana_formatada"]}</strong></span>
                <span class="rt-stat">⚡ Rápida: {rt["mais_rapida"]}</span>
                <span class="rt-stat">🕔 Lenta: {rt["mais_lenta"]}</span>
                <span class="rt-count">{rt["total_respostas"]} respostas</span>
            </div>'''
        else:
            response_time_html = '<div class="stats-note">Sem dados suficientes de tempo de resposta</div>'

        # Heatmap (dia x hora)
        dias_semana_hm = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        flat_values = [v for row in heatmap for v in row]
        max_heat = max(flat_values) if flat_values and max(flat_values) > 0 else 1
        heatmap_cells = ""
        for day_idx, day_data in enumerate(heatmap):
            heatmap_cells += f'<div class="hm-label">{dias_semana_hm[day_idx]}</div>'
            for h, count in enumerate(day_data):
                intensity = count / max_heat if max_heat > 0 else 0
                pct_of_total = round(intensity * 100, 1)
                # White → Blue → Red gradient
                if intensity == 0:
                    bg_color = "#f5f5f5"
                elif intensity < 0.5:
                    t2 = intensity * 2
                    r = int(245 - t2 * 183)  # 245→62
                    g = int(245 - t2 * 117)  # 245→128
                    b = int(245 - t2 * 15)   # 245→230
                    bg_color = f"rgb({r},{g},{b})"
                else:
                    t2 = (intensity - 0.5) * 2
                    r = int(62 + t2 * 169)   # 62→231
                    g = int(128 - t2 * 52)   # 128→76
                    b = int(230 - t2 * 170)  # 230→60
                    bg_color = f"rgb({r},{g},{b})"
                text_color = "#fff" if intensity > 0.3 else "#555"
                heatmap_cells += f'<div class="hm-cell" style="background:{bg_color};color:{text_color}" title="{dias_semana_hm[day_idx]} {h:02d}h: {count} msgs ({pct_of_total}%)">{count if count > 0 else ""}</div>'
        heatmap_header = '<div class="hm-label"></div>'
        for h in range(24):
            heatmap_header += f'<div class="hm-hour">{h}</div>'
        heatmap_html = f'''<div class="heatmap-container">
            <div class="hm-grid">{heatmap_header}{heatmap_cells}</div>
        </div>'''

        # Reações
        reacoes_html = ""
        if reacoes["total"] > 0:
            max_r = reacoes["por_autor"][0]["total"] if reacoes["por_autor"] else 1
            for r in reacoes["por_autor"]:
                pct = (r["total"] / max_r) * 100
                reacoes_html += f'''
            <div class="bar-row">
                <div class="bar-label">{r["nome"][:20]}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%"></div>
                </div>
                <div class="bar-value">{r["total"]:,}</div>
            </div>'''
        else:
            reacoes_html = '<div class="stats-note">Nenhuma reação encontrada</div>'

        # Emojis
        emojis_cloud_html = ""
        if emojis["total_emojis"] > 0:
            for i, e in enumerate(emojis["top_30"]):
                size = max(16, 40 - i)
                emojis_cloud_html += f'<span class="emoji-tag" style="font-size:{size}px" title="{e["contagem"]}x">{e["emoji"]} <small>{e["contagem"]}</small></span> '
            emojis_by_author_html = ""
            for ea in emojis["por_autor"][:8]:
                top3 = " ".join(ea["top_3"])
                emojis_by_author_html += f'''
            <div class="emoji-author-row">
                <span class="emoji-author-name">{ea["nome"][:20]}</span>
                <span class="emoji-author-fav">{top3}</span>
                <span class="emoji-author-count">{ea["total"]:,}</span>
            </div>'''
        else:
            emojis_cloud_html = '<div class="stats-note">Nenhum emoji encontrado</div>'
            emojis_by_author_html = ""

        # Integridade de anexos
        integrity_missing_html = ""
        if integridade["faltando"] > 0:
            for m in integridade["faltando_lista"][:10]:
                integrity_missing_html += f'<div class="integrity-missing"><span>\u274c {m["arquivo"]}</span><span class="integrity-meta">{m["autor"]} - {m["data"]}</span></div>'

        # Gaps de conversa
        gaps_html = ""
        if gaps["total_gaps"] > 0:
            for g in gaps["gaps"][:20]:
                gaps_html += (
                    f'<div class="gap-item">'
                    f'<span class="gap-conv">{g["conversa"]}</span>'
                    f'<span class="gap-period">{g["de"]} → {g["ate"]}</span>'
                    f'<span class="gap-days">{g["dias"]} dias</span>'
                    f'</div>'
                )
        else:
            gaps_html = '<div class="stats-note">Nenhum gap de inatividade ≥ 30 dias encontrado</div>'

        gaps_summary = ""
        if gaps["maior_gap"]:
            gaps_summary = (
                f'<div class="stats-note">Maior gap: <strong>{gaps["maior_gap"]["dias"]} dias</strong> '
                f'em {gaps["maior_gap"]["conversa"]} ({gaps["maior_gap"]["de"]} → {gaps["maior_gap"]["ate"]})'
                f' • {gaps["total_gaps"]} gaps em {gaps["conversas_com_gaps"]} conversas</div>'
            )

        # Distribuição de tamanho de mensagens
        dist = tamanho_msgs["distribuicao"]
        max_dist = max(dist.values()) if dist else 1
        msg_length_html = ""
        for label in tamanho_msgs["faixas"]:
            count = dist.get(label, 0)
            pct = count / max(max_dist, 1) * 100
            msg_length_html += (
                f'<div class="msg-len-row">'
                f'<span class="msg-len-label">{label}</span>'
                f'<div class="msg-len-bar-bg"><div class="msg-len-bar-fill" style="width:{pct:.1f}%"></div></div>'
                f'<span class="msg-len-count">{count:,}</span>'
                f'</div>'
            )

        # Comparação entre períodos
        comparacao_html = ""
        if comparacao.get("ativo"):
            rows_data = [
                ("Mensagens", comparacao["p1"]["msgs"], comparacao["p2"]["msgs"], comparacao["variacoes"]["msgs"]),
                ("Anexos", comparacao["p1"]["anexos"], comparacao["p2"]["anexos"], comparacao["variacoes"]["anexos"]),
                ("Chamadas", comparacao["p1"]["chamadas"], comparacao["p2"]["chamadas"], comparacao["variacoes"]["chamadas"]),
                ("Participantes", comparacao["p1"]["autores"], comparacao["p2"]["autores"], comparacao["variacoes"]["autores"]),
                ("Média chars/msg", comparacao["p1"]["media_len"], comparacao["p2"]["media_len"], comparacao["variacoes"]["media_len"]),
            ]
            comparacao_rows = ""
            for label, v1, v2, var in rows_data:
                color = "#4CAF50" if var.startswith("+") else "#f44336" if var.startswith("-") else "#888"
                comparacao_rows += (
                    f'<tr><td>{label}</td>'
                    f'<td style="text-align:right">{v1:,}</td>'
                    f'<td style="text-align:right">{v2:,}</td>'
                    f'<td style="text-align:right;color:{color};font-weight:700">{var}</td></tr>'
                )
            comparacao_html = f'''
                <div class="stats-section">
                    <h3>📊 Comparação entre Períodos</h3>
                    <table class="comp-table">
                        <thead>
                            <tr>
                                <th>Métrica</th>
                                <th>1ª metade<br><small>{comparacao["p1_de"]} → {comparacao["p1_ate"]}</small></th>
                                <th>2ª metade<br><small>{comparacao["p2_de"]} → {comparacao["p2_ate"]}</small></th>
                                <th>Variação</th>
                            </tr>
                        </thead>
                        <tbody>{comparacao_rows}</tbody>
                    </table>
                </div>'''

        # Idiomas
        idiomas_html = ""
        if idiomas.get("percentuais"):
            lang_bars = ""
            for lang, pct in idiomas["percentuais"].items():
                lang_bars += (
                    f'<div class="msg-len-row">'
                    f'<span class="msg-len-label">{lang}</span>'
                    f'<div class="msg-len-bar-bg"><div class="msg-len-bar-fill" style="width:{pct}%"></div></div>'
                    f'<span class="msg-len-count">{pct}%</span>'
                    f'</div>'
                )
            idiomas_html = lang_bars
        else:
            idiomas_html = '<div class="stats-note">Dados insuficientes para detectar idioma</div>'

        # Timeline visual de conversas
        timeline_html = ""
        if timeline and len(timeline) >= 2:
            import html as html_mod
            # Compute global time range
            all_starts = [t["start"] for t in timeline]
            all_ends = [t["end"] for t in timeline]
            global_start = min(all_starts)
            global_end = max(all_ends)
            total_span = (global_end - global_start).total_seconds()
            if total_span <= 0:
                total_span = 1
            max_count = max(t["count"] for t in timeline)
            # Show top 20 by message count
            top_timeline = sorted(timeline, key=lambda x: x["count"], reverse=True)[:20]
            top_timeline.sort(key=lambda x: x["start"])
            for t_item in top_timeline:
                left_pct = ((t_item["start"] - global_start).total_seconds() / total_span) * 100
                width_pct = max(((t_item["end"] - t_item["start"]).total_seconds() / total_span) * 100, 0.5)
                intensity = t_item["count"] / max_count if max_count > 0 else 0
                # Blue to purple gradient based on volume
                r = int(74 + intensity * 65)
                g = int(144 - intensity * 52)
                b = int(217 + intensity * 29)
                name = html_mod.escape(t_item["name"][:25])
                start_str = t_item["start"].strftime("%d/%m/%Y")
                end_str = t_item["end"].strftime("%d/%m/%Y")
                timeline_html += (
                    f'<div class="tl-row">'
                    f'<span class="tl-name" title="{html_mod.escape(t_item["name"])}">{name}</span>'
                    f'<div class="tl-track">'
                    f'<div class="tl-bar" style="left:{left_pct:.1f}%;width:{width_pct:.1f}%;background:rgb({r},{g},{b})" '
                    f'title="{start_str} → {end_str} • {t_item["count"]:,} msgs"></div>'
                    f'</div>'
                    f'<span class="tl-count">{t_item["count"]:,}</span>'
                    f'</div>'
                )
            # Axis labels
            mid_date = global_start + (global_end - global_start) / 2
            timeline_html += (
                f'<div class="tl-axis">'
                f'<span>{global_start.strftime("%b %Y")}</span>'
                f'<span>{mid_date.strftime("%b %Y")}</span>'
                f'<span>{global_end.strftime("%b %Y")}</span>'
                f'</div>'
            )

        return f'''
        <div class="stats-panel" id="stats-panel" style="display:none;">
            <div class="stats-container">
                <h2 class="stats-title">📊 Estatísticas das Conversas</h2>

                <div class="stats-section">
                    <h3>📋 Resumo Geral</h3>
                    {cards_html}
                </div>

                <div class="stats-section">
                    <h3>👥 Top Participantes</h3>
                    <div class="bars-container">
                        {participants_html}
                    </div>
                </div>

                <div class="stats-row">
                    <div class="stats-section stats-half">
                        <h3>⏰ Atividade por Hora</h3>
                        <div class="hours-chart">
                            {hours_html}
                        </div>
                        <div class="hours-labels">{hour_labels}</div>
                        <div class="stats-note">Hora mais ativa: <strong>{horarios["hora_mais_ativa"]}</strong></div>
                    </div>

                    <div class="stats-section stats-half">
                        <h3>📅 Atividade por Dia</h3>
                        <div class="weekdays-chart">
                            {weekdays_html}
                        </div>
                        <div class="stats-note">Dia mais ativo: <strong>{temporal["dia_mais_ativo"]}</strong></div>
                    </div>
                </div>

                <div class="stats-section">
                    <h3>📈 Atividade Mensal</h3>
                    <div class="monthly-chart">
                        {monthly_html}
                    </div>
                </div>

                <div class="stats-row">
                    <div class="stats-section stats-half">
                        <h3>📷 Mídias</h3>
                        {midias_html}
                    </div>

                    <div class="stats-section stats-half">
                        <h3>📞 Chamadas</h3>
                        {chamadas_html}
                    </div>
                </div>

                <div class="stats-section">
                    <h3>💬 Palavras Mais Usadas</h3>
                    <div class="words-cloud">
                        {words_html}
                    </div>
                    <div class="stats-note">Total: {palavras["total_palavras"]:,} palavras • {palavras["palavras_unicas"]:,} únicas</div>
                </div>

                <div class="stats-section">
                    <h3>🏆 Top Conversas</h3>
                    <div class="top-conversations">
                        {top_html}
                    </div>
                </div>

                {f"""<div class="stats-section">
                    <h3>📅 Timeline de Conversas</h3>
                    <div class="tl-container">{timeline_html}</div>
                    <div class="stats-note">Top 20 conversas por volume de mensagens</div>
                </div>""" if timeline_html else ""}

                <div class="stats-section">
                    <h3>⏱️ Tempo de Resposta (DMs)</h3>
                    <div class="response-times">
                        {response_time_html}
                    </div>
                </div>

                <div class="stats-section">
                    <h3>🗓️ Mapa de Calor - Atividade</h3>
                    {heatmap_html}
                </div>

                <div class="stats-section">
                    <h3>❤️ Reações</h3>
                    <div class="bars-container">
                        {reacoes_html}
                    </div>
                    <div class="stats-note">Total: {reacoes["total"]:,} reações</div>
                </div>

                <div class="stats-section">
                    <h3>😀 Emojis Mais Usados</h3>
                    <div class="emoji-cloud">
                        {emojis_cloud_html}
                    </div>
                    {f'<div class="emoji-authors">{emojis_by_author_html}</div>' if emojis_by_author_html else ''}
                    <div class="stats-note">Total: {emojis["total_emojis"]:,} emojis • {emojis["emojis_unicos"]} únicos • {emojis["msgs_com_emoji"]:,} msgs com emoji</div>
                </div>

                <div class="stats-section">
                    <h3>📎 Integridade de Anexos</h3>
                    <div class="integrity-stats">
                        <div class="integrity-bar">
                            <div class="integrity-fill" style="width:{integridade['percentual_ok']}%"></div>
                        </div>
                        <div class="integrity-info">
                            ✅ {integridade['encontrados']}/{integridade['total']} arquivos encontrados ({integridade['percentual_ok']}%)
                            {f' • ❌ {integridade["faltando"]} faltando' if integridade['faltando'] > 0 else ''}
                        </div>
                    </div>
                    {integrity_missing_html}
                </div>

                <div class="stats-section">
                    <h3>⏸️ Gaps de Inatividade (≥ {gaps["min_dias"]} dias)</h3>
                    <div class="gaps-container">
                        {gaps_html}
                    </div>
                    {gaps_summary}
                </div>

                <div class="stats-section">
                    <h3>🕸️ Grafo de Relacionamentos</h3>
                    {grafo["svg"] if grafo["svg"] else '<div class="stats-note">Dados insuficientes para gerar o grafo</div>'}
                    {f'<div class="stats-note">{grafo["total_nos"]} participantes • {grafo["total_conexoes"]} conexões</div>' if grafo["svg"] else ''}
                </div>

                <div class="stats-section">
                    <h3>📏 Distribuição de Tamanho das Mensagens</h3>
                    <div class="msg-len-chart">
                        {msg_length_html}
                    </div>
                    <div class="stats-note">Média: <strong>{tamanho_msgs["media_chars"]}</strong> chars/msg • {tamanho_msgs["total_msgs_com_texto"]:,} msgs com texto</div>
                </div>

                {comparacao_html}

                <div class="stats-section">
                    <h3>🌐 Idiomas Detectados</h3>
                    <div class="msg-len-chart">
                        {idiomas_html}
                    </div>
                    <div class="stats-note">Idioma principal: <strong>{idiomas["principal"]}</strong> (detecção por palavras-chave)</div>
                </div>
            </div>
        </div>'''

    @staticmethod
    def get_stats_css() -> str:
        """Retorna CSS para o painel de estatísticas"""
        return '''
        .stats-panel {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 2500;
            overflow-y: auto;
            padding: 30px;
        }

        .stats-container {
            max-width: 1000px;
            margin: 0 auto;
            background: #fff;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }

        .stats-title {
            font-size: 24px;
            color: #333;
            margin-bottom: 25px;
            text-align: center;
        }

        .stats-section {
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f8f8;
            border-radius: 12px;
        }

        .stats-section h3 {
            font-size: 16px;
            color: #444;
            margin-bottom: 15px;
        }

        .stats-row {
            display: flex;
            gap: 20px;
        }

        .stats-half {
            flex: 1;
            min-width: 0;
        }

        .stats-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
        }

        .stat-card {
            background: #fff;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .stat-number {
            font-size: 24px;
            font-weight: 700;
            color: #333;
        }

        .stat-label {
            font-size: 11px;
            color: #888;
            margin-top: 4px;
        }

        .stats-period {
            text-align: center;
            font-size: 12px;
            color: #888;
            margin-top: 10px;
        }

        /* Barras horizontais */
        .bars-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .bar-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .bar-label {
            width: 120px;
            font-size: 12px;
            color: #555;
            text-align: right;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .bar-track {
            flex: 1;
            height: 20px;
            background: #e8e8e8;
            border-radius: 10px;
            overflow: hidden;
        }

        .bar-fill {
            height: 100%;
            background: linear-gradient(135deg, #555, #777);
            border-radius: 10px;
            transition: width 0.5s ease;
        }

        .bar-value {
            width: 60px;
            font-size: 12px;
            font-weight: 600;
            color: #444;
        }

        /* Gráfico de horas */
        .hours-chart {
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 120px;
            padding: 0 5px;
        }

        .hour-bar {
            flex: 1;
            background: linear-gradient(180deg, #555, #888);
            border-radius: 3px 3px 0 0;
            min-height: 2px;
            transition: height 0.3s ease;
        }

        .hour-bar:hover {
            background: linear-gradient(180deg, #333, #666);
        }

        .hours-labels {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #999;
            padding: 4px 5px 0;
        }

        /* Dias da semana */
        .weekdays-chart {
            display: flex;
            align-items: flex-end;
            justify-content: space-around;
            height: 120px;
            gap: 8px;
        }

        .weekday-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
        }

        .weekday-bar-track {
            width: 100%;
            height: 90px;
            background: #e8e8e8;
            border-radius: 6px;
            display: flex;
            align-items: flex-end;
            overflow: hidden;
        }

        .weekday-bar-fill {
            width: 100%;
            background: linear-gradient(180deg, #555, #888);
            border-radius: 6px 6px 0 0;
            min-height: 2px;
        }

        .weekday-label {
            font-size: 11px;
            color: #666;
            margin-top: 4px;
            font-weight: 500;
        }

        .weekday-value {
            font-size: 10px;
            color: #999;
        }

        /* Atividade mensal */
        .monthly-chart {
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 100px;
            overflow-x: auto;
            padding-bottom: 5px;
        }

        .month-bar-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 30px;
            flex: 1;
        }

        .month-bar-track {
            width: 100%;
            height: 80px;
            display: flex;
            align-items: flex-end;
        }

        .month-bar-fill {
            width: 100%;
            background: linear-gradient(180deg, #555, #888);
            border-radius: 3px 3px 0 0;
            min-height: 2px;
        }

        .month-label {
            font-size: 9px;
            color: #999;
            margin-top: 3px;
            writing-mode: vertical-rl;
            transform: rotate(180deg);
            height: 40px;
        }

        /* Mídias */
        .media-stats {
            display: flex;
            gap: 15px;
            justify-content: center;
        }

        .media-stat-item {
            text-align: center;
            padding: 15px 20px;
            background: #fff;
            border-radius: 10px;
            min-width: 80px;
        }

        .media-stat-icon {
            font-size: 28px;
        }

        .media-stat-value {
            font-size: 20px;
            font-weight: 700;
            color: #333;
        }

        .media-stat-label {
            font-size: 11px;
            color: #888;
        }

        /* Chamadas */
        .calls-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .call-stat {
            background: #fff;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 13px;
            color: #555;
        }

        /* Palavras */
        .words-cloud {
            text-align: center;
            line-height: 2.8;
            padding: 15px 10px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: baseline;
            gap: 4px;
        }

        .word-tag {
            display: inline-block;
            background: #fff;
            padding: 4px 12px;
            border-radius: 20px;
            margin: 2px;
            white-space: nowrap;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        .word-tag:hover {
            transform: scale(1.08);
            box-shadow: 0 3px 10px rgba(0,0,0,0.15);
        }

        .word-tag small {
            font-size: 10px;
            color: #999;
        }

        /* Top conversas */
        .top-conversations {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .top-conv-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 12px;
            background: #fff;
            border-radius: 8px;
        }

        .top-rank {
            font-weight: 700;
            color: #888;
            width: 30px;
        }

        .top-name {
            flex: 1;
            font-size: 13px;
            color: #444;
        }

        .top-msgs {
            font-size: 12px;
            font-weight: 600;
            color: #666;
        }

        .stats-note {
            font-size: 11px;
            color: #999;
            margin-top: 8px;
            text-align: center;
        }

        @media (max-width: 768px) {
            .stats-row {
                flex-direction: column;
            }
            .bar-label {
                width: 80px;
            }
        }

        /* Heatmap */
        .heatmap-container {
            overflow-x: auto;
        }
        .hm-grid {
            display: grid;
            grid-template-columns: 40px repeat(24, 1fr);
            gap: 2px;
            min-width: 600px;
        }
        .hm-label {
            font-size: 11px;
            color: #666;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 500;
        }
        .hm-hour {
            font-size: 9px;
            color: #999;
            text-align: center;
        }
        .hm-cell {
            border-radius: 3px;
            font-size: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #555;
            min-height: 22px;
        }

        /* Tempo de resposta */
        .response-times {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .rt-row {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 15px;
            background: #fff;
            border-radius: 8px;
            flex-wrap: wrap;
        }
        .rt-name {
            width: 130px;
            font-weight: 600;
            font-size: 13px;
            color: #444;
        }
        .rt-stat {
            font-size: 12px;
            color: #666;
        }
        .rt-count {
            font-size: 11px;
            color: #999;
            margin-left: auto;
        }

        /* Emojis */
        .emoji-cloud {
            text-align: center;
            line-height: 2.8;
            padding: 10px;
        }
        .emoji-tag {
            display: inline-block;
            padding: 2px 6px;
            margin: 2px;
            cursor: default;
        }
        .emoji-tag small {
            font-size: 10px;
            color: #999;
        }
        .emoji-authors {
            margin-top: 15px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .emoji-author-row {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 15px;
            background: #fff;
            border-radius: 8px;
        }
        .emoji-author-name {
            width: 130px;
            font-weight: 600;
            font-size: 13px;
            color: #444;
        }
        .emoji-author-fav {
            font-size: 20px;
            flex: 1;
        }
        .emoji-author-count {
            font-size: 12px;
            color: #888;
            font-weight: 600;
        }

        /* Integridade de anexos */
        .integrity-stats {
            margin-bottom: 12px;
        }
        .integrity-bar {
            height: 12px;
            background: #e8e8e8;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .integrity-fill {
            height: 100%;
            background: linear-gradient(135deg, #4CAF50, #66BB6A);
            border-radius: 6px;
        }
        .integrity-info {
            font-size: 13px;
            color: #555;
            text-align: center;
        }
        .integrity-missing {
            display: flex;
            justify-content: space-between;
            padding: 6px 12px;
            background: #fff3f3;
            border-radius: 6px;
            margin-top: 4px;
            font-size: 12px;
            color: #c62828;
        }
        .integrity-meta {
            color: #999;
            font-size: 11px;
        }

        /* Gaps de inatividade */
        .gaps-container {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .gap-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 14px;
            background: #f9f5e8;
            border-radius: 6px;
            font-size: 13px;
            border-left: 3px solid #ff9800;
        }
        .gap-conv {
            flex: 1;
            font-weight: 600;
            color: #444;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 300px;
        }
        .gap-period {
            color: #777;
            font-size: 12px;
            white-space: nowrap;
        }
        .gap-days {
            font-weight: 700;
            color: #e65100;
            min-width: 70px;
            text-align: right;
            white-space: nowrap;
        }

        /* Distribuição de tamanho de mensagens */
        .msg-len-chart {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .msg-len-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .msg-len-label {
            width: 80px;
            font-size: 12px;
            font-weight: 600;
            color: #555;
            text-align: right;
        }
        .msg-len-bar-bg {
            flex: 1;
            height: 18px;
            background: #e8e8e8;
            border-radius: 4px;
            overflow: hidden;
        }
        .msg-len-bar-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 4px;
            transition: width 0.3s;
        }
        .msg-len-count {
            width: 60px;
            font-size: 12px;
            font-weight: 600;
            color: #444;
        }

        /* Comparação entre períodos */
        .comp-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .comp-table th, .comp-table td {
            padding: 10px 14px;
            border-bottom: 1px solid #e0e0e0;
        }
        .comp-table th {
            background: #f5f5f5;
            font-weight: 600;
            color: #444;
            text-align: left;
        }
        .comp-table th small {
            font-weight: 400;
            color: #888;
            font-size: 11px;
        }
        .comp-table td {
            color: #333;
        }
        .comp-table tbody tr:hover {
            background: #f9f9ff;
        }

        /* Timeline de conversas */
        .tl-container {
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 10px 0;
        }
        .tl-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tl-name {
            width: 130px;
            font-size: 11px;
            font-weight: 600;
            color: #555;
            text-align: right;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .tl-track {
            flex: 1;
            height: 16px;
            background: #f0f0f0;
            border-radius: 3px;
            position: relative;
            overflow: hidden;
        }
        .tl-bar {
            position: absolute;
            height: 100%;
            border-radius: 3px;
            min-width: 3px;
            transition: opacity 0.2s;
            cursor: default;
        }
        .tl-bar:hover {
            opacity: 0.8;
            box-shadow: 0 0 6px rgba(0,0,0,0.3);
        }
        .tl-count {
            width: 55px;
            font-size: 11px;
            font-weight: 600;
            color: #666;
            text-align: right;
        }
        .tl-axis {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #999;
            padding: 4px 140px 0 140px;
        }
        @media (max-width: 768px) {
            .tl-name { width: 80px; font-size: 10px; }
            .tl-axis { padding: 4px 90px 0 90px; }
        }
        '''

    @staticmethod
    def get_stats_js() -> str:
        """Retorna JavaScript para o painel de estatísticas"""
        return '''
        function toggleStatsPanel() {
            const panel = document.getElementById('stats-panel');
            if (panel.style.display === 'none') {
                panel.style.display = 'block';
            } else {
                panel.style.display = 'none';
            }
        }

        // Fechar stats com ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const panel = document.getElementById('stats-panel');
                if (panel && panel.style.display !== 'none') {
                    panel.style.display = 'none';
                }
            }
        });

        // Fechar stats clicando no fundo
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('stats-panel')) {
                e.target.style.display = 'none';
            }
        });
        '''
