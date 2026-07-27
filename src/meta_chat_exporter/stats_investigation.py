"""
Métricas de investigação (A1–A10, A5).

Funções puras sobre threads/acumuladores, consumidas por ``ChatStatistics``
para manter ``stats.py`` mais enxuto e facilitar testes/tipagem.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from meta_chat_exporter.models import Thread


def stats_timeline_contatos(
    threads: list[Thread],
    owner_username: str,
) -> list[dict[str, Any]]:
    """A1 — Timeline de contatos: primeira e última mensagem de cada contato."""
    if not owner_username:
        return []

    contato_first: dict[str, datetime] = {}
    contato_last: dict[str, datetime] = {}
    contato_msgs: Counter[str] = Counter()

    for t in threads:
        for msg in t.messages:
            if not msg.sent or not msg.author:
                continue
            author = msg.author
            if author == owner_username:
                continue
            contato_msgs[author] += 1
            if author not in contato_first or msg.sent < contato_first[author]:
                contato_first[author] = msg.sent
            if author not in contato_last or msg.sent > contato_last[author]:
                contato_last[author] = msg.sent

    result: list[dict[str, Any]] = []
    for name, total in contato_msgs.most_common():
        result.append(
            {
                "nome": name,
                "primeira_msg": contato_first[name].strftime("%d/%m/%Y %H:%M"),
                "ultima_msg": contato_last[name].strftime("%d/%m/%Y %H:%M"),
                "total_mensagens": total,
            }
        )
    return result


def stats_atividade_noturna(
    noturna_por_autor: Counter[str],
    total_noturna: int,
) -> dict[str, Any]:
    """A2 — Atividade noturna a partir de acumuladores single-pass."""
    por_autor = [
        {"nome": name, "mensagens": count}
        for name, count in noturna_por_autor.most_common(20)
    ]
    return {
        "total_noturna": total_noturna,
        "por_autor": por_autor,
    }


def stats_taxa_resposta(
    threads: list[Thread],
    owner_username: str,
) -> list[dict[str, Any]]:
    """A4 — Taxa de resposta em DMs (janela 24h, pula rajadas do mesmo autor)."""
    if not owner_username:
        return []

    result: list[dict[str, Any]] = []

    for thread in threads:
        if len(thread.participants) != 2:
            continue

        msgs = [m for m in thread.messages if m.sent and not m.is_call and not m.is_reaction]
        if len(msgs) < 2:
            continue

        msgs.sort(key=lambda m: m.sent or datetime.min)

        other_name = ""
        for p in thread.participants:
            if p[0] != owner_username:
                other_name = p[0]
                break
        if not other_name:
            continue

        owner_sent = 0
        owner_answered = 0
        other_sent = 0
        other_answered = 0

        for i, curr in enumerate(msgs):
            curr_is_owner = curr.author == owner_username
            if curr_is_owner:
                owner_sent += 1
            else:
                other_sent += 1

            for j in range(i + 1, len(msgs)):
                nxt = msgs[j]
                if nxt.author == curr.author:
                    continue
                assert curr.sent is not None and nxt.sent is not None
                delta = (nxt.sent - curr.sent).total_seconds()
                if 0 < delta <= 86400:
                    if curr_is_owner:
                        other_answered += 1
                    else:
                        owner_answered += 1
                break

        taxa_owner = round(owner_answered / max(other_sent, 1) * 100, 1)
        taxa_other = round(other_answered / max(owner_sent, 1) * 100, 1)

        result.append(
            {
                "nome": other_name,
                "msgs_alvo": owner_sent,
                "msgs_contato": other_sent,
                "respostas_alvo": owner_answered,
                "respostas_contato": other_answered,
                "taxa_resposta_alvo": taxa_owner,
                "taxa_resposta_contato": taxa_other,
            }
        )

    result.sort(key=lambda x: x["taxa_resposta_alvo"], reverse=True)
    return result


def stats_timeline_links(threads: list[Thread]) -> list[dict[str, Any]]:
    """A8 — Timeline cronológica de links compartilhados."""
    items: list[dict[str, Any]] = []
    for t in threads:
        conv = t.thread_name or (t.participants[0].username if t.participants else t.thread_id)
        for msg in t.messages:
            if not msg.share_url:
                continue
            host = ""
            try:
                host = urlparse(msg.share_url).hostname or ""
            except ValueError:
                host = ""
            items.append(
                {
                    "data": msg.sent.strftime("%d/%m/%Y %H:%M") if msg.sent else "",
                    "autor": msg.author,
                    "url": msg.share_url,
                    "dominio": host,
                    "conversa": conv,
                    "timestamp": msg.sent,
                }
            )
    items.sort(key=lambda x: x["timestamp"] or datetime.min)
    for row in items:
        row.pop("timestamp", None)
    return items


def stats_dominancia_grupo(threads: list[Thread]) -> list[dict[str, Any]]:
    """A9 — Dominância em grupos: % de mensagens por participante."""
    result: list[dict[str, Any]] = []
    for t in threads:
        if len(t.participants) <= 2:
            continue
        total = len(t.messages)
        if total == 0:
            continue
        counts: Counter[str] = Counter()
        for msg in t.messages:
            if msg.author:
                counts[msg.author] += 1
        if not counts:
            continue
        conv = t.thread_name or ", ".join(p[0] for p in t.participants[:3])
        participantes = [
            {
                "nome": name,
                "mensagens": count,
                "percentual": round(count / total * 100, 1),
            }
            for name, count in counts.most_common()
        ]
        result.append(
            {
                "conversa": conv,
                "thread_id": t.thread_id,
                "total_mensagens": total,
                "participantes": participantes,
                "dominante": participantes[0]["nome"] if participantes else "",
                "pct_dominante": participantes[0]["percentual"] if participantes else 0.0,
            }
        )
    result.sort(key=lambda x: x["pct_dominante"], reverse=True)
    return result


def stats_midia_por_contato(
    participant_stats: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """A10 — Padrão de mídia por contato (fotos/áudios/vídeos/links)."""
    result: list[dict[str, Any]] = []
    for name, data in participant_stats.items():
        fotos = data.get("fotos", 0)
        audios = data.get("audios", 0)
        videos = data.get("videos", 0)
        links = data.get("links", 0)
        total_midia = fotos + audios + videos + links
        if total_midia == 0:
            continue
        tipos = {"fotos": fotos, "audios": audios, "videos": videos, "links": links}
        predominante = max(tipos, key=tipos.get)  # type: ignore[arg-type]
        result.append(
            {
                "nome": name,
                "fotos": fotos,
                "audios": audios,
                "videos": videos,
                "links": links,
                "total_midia": total_midia,
                "tipo_predominante": predominante,
            }
        )
    result.sort(key=lambda x: x["total_midia"], reverse=True)
    return result


def stats_velocidade_conversa(
    threads: list[Thread],
    *,
    gap_minutes: int = 30,
) -> list[dict[str, Any]]:
    """A5 — Velocidade de conversa: msgs/hora em sessões ativas.

    Uma sessão ativa é um bloco de mensagens com gap < ``gap_minutes`` entre
    consecutivas. A velocidade é total_msgs / duração_horas da sessão (mínimo
    1 minuto de duração para evitar divisão por zero).

    Retorna por conversa: número de sessões, msgs/hora média e pico.
    """
    result: list[dict[str, Any]] = []
    gap_sec = gap_minutes * 60

    for t in threads:
        dated = sorted((m for m in t.messages if m.sent), key=lambda m: m.sent or datetime.min)
        if len(dated) < 2:
            continue

        sessions: list[list] = []
        current = [dated[0]]
        for prev, msg in zip(dated, dated[1:], strict=False):
            assert prev.sent is not None and msg.sent is not None
            if (msg.sent - prev.sent).total_seconds() <= gap_sec:
                current.append(msg)
            else:
                if len(current) >= 2:
                    sessions.append(current)
                current = [msg]
        if len(current) >= 2:
            sessions.append(current)

        if not sessions:
            continue

        rates: list[float] = []
        for sess in sessions:
            start = sess[0].sent
            end = sess[-1].sent
            assert start is not None and end is not None
            duration_h = max((end - start).total_seconds() / 3600.0, 1.0 / 60.0)
            rates.append(len(sess) / duration_h)

        conv = t.thread_name or (t.participants[0].username if t.participants else t.thread_id)
        result.append(
            {
                "conversa": conv,
                "thread_id": t.thread_id,
                "num_sessoes": len(sessions),
                "msgs_por_hora_media": round(sum(rates) / len(rates), 1),
                "msgs_por_hora_pico": round(max(rates), 1),
                "total_msgs_ativas": sum(len(s) for s in sessions),
            }
        )

    result.sort(key=lambda x: x["msgs_por_hora_pico"], reverse=True)
    return result


def _conversation_label(thread: Thread) -> str:
    if thread.thread_name:
        return thread.thread_name
    if thread.participants:
        return thread.participants[0].username
    return thread.thread_id


def stats_iniciadores(threads: list[Thread]) -> list[dict[str, Any]]:
    """A3 — Quem iniciou cada conversa (primeira mensagem datada)."""
    result: list[dict[str, Any]] = []
    for t in threads:
        dated = sorted((m for m in t.messages if m.sent and m.author), key=lambda m: m.sent or datetime.min)
        if not dated:
            continue
        first = dated[0]
        assert first.sent is not None
        result.append(
            {
                "conversa": _conversation_label(t),
                "thread_id": t.thread_id,
                "iniciador": first.author,
                "data_inicio": first.sent.strftime("%d/%m/%Y %H:%M"),
                "total_mensagens": len(t.messages),
            }
        )
    result.sort(key=lambda x: x["data_inicio"])
    return result


def stats_rajadas(
    threads: list[Thread],
    *,
    min_size: int = 3,
) -> list[dict[str, Any]]:
    """A6 — Rajadas: sequências consecutivas do mesmo autor (mín. ``min_size``)."""
    result: list[dict[str, Any]] = []
    for t in threads:
        dated = sorted(
            (m for m in t.messages if m.sent and m.author and not m.is_call and not m.is_reaction),
            key=lambda m: m.sent or datetime.min,
        )
        if len(dated) < min_size:
            continue

        bursts: list[dict[str, Any]] = []
        run_author = dated[0].author
        run_start = dated[0].sent
        run_len = 1
        for msg in dated[1:]:
            if msg.author == run_author:
                run_len += 1
            else:
                if run_len >= min_size and run_start is not None:
                    bursts.append(
                        {
                            "autor": run_author,
                            "tamanho": run_len,
                            "inicio": run_start.strftime("%d/%m/%Y %H:%M"),
                        }
                    )
                run_author = msg.author
                run_start = msg.sent
                run_len = 1
        if run_len >= min_size and run_start is not None:
            bursts.append(
                {
                    "autor": run_author,
                    "tamanho": run_len,
                    "inicio": run_start.strftime("%d/%m/%Y %H:%M"),
                }
            )

        if not bursts:
            continue

        max_burst = max(b["tamanho"] for b in bursts)
        by_author: Counter[str] = Counter()
        for b in bursts:
            by_author[str(b["autor"])] += 1

        result.append(
            {
                "conversa": _conversation_label(t),
                "thread_id": t.thread_id,
                "num_rajadas": len(bursts),
                "maior_rajada": max_burst,
                "autor_mais_rajadas": by_author.most_common(1)[0][0] if by_author else "",
                "rajadas": sorted(bursts, key=lambda b: b["tamanho"], reverse=True)[:10],
            }
        )

    result.sort(key=lambda x: x["maior_rajada"], reverse=True)
    return result


def stats_removidas_por_autor(threads: list[Thread]) -> list[dict[str, Any]]:
    """A7 — Mensagens removidas pelo remetente, agregadas por autor."""
    counts: Counter[str] = Counter()
    for t in threads:
        for msg in t.messages:
            if msg.removed_by_sender and msg.author:
                counts[msg.author] += 1

    total = sum(counts.values())
    result: list[dict[str, Any]] = []
    for name, n in counts.most_common():
        result.append(
            {
                "nome": name,
                "removidas": n,
                "percentual": round(n / max(total, 1) * 100, 1),
            }
        )
    return result
