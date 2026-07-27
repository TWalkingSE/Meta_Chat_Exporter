"""
Meta Chat Exporter - Renderização do relatório HTML de estatísticas.

Camada de apresentação separada de stats.py (camada de dados). Recebe o dict
produzido por ChatStatistics.generate_all() e devolve HTML/CSS/JS.
"""

from meta_chat_exporter.utils import escape_html


class StatsReportRenderer:
    """Renderiza o painel de estatísticas a partir de ChatStatistics.generate_all()."""

    @staticmethod
    def render_html_report(stats: dict, *, filtro: object | None = None) -> str:
        """Gera um relatório HTML completo com gráficos CSS.

        Args:
            stats: dicionário produzido por ``ChatStatistics.generate_all()``. Já
                pode ser o resultado recalculado sobre um subconjunto filtrado
                (ver ``ChatStatistics.filtrar``) — R19.1, R19.2.
            filtro: descrição opcional do filtro aplicado (``StatsFilter`` ou
                ``dict`` com ``thread_id``/``data_inicio``/``data_fim``). Usado
                apenas para apresentação: exibe um aviso do filtro vigente. Quando
                ``None`` o relatório reflete o conjunto global (R19.3).

        Quando o conjunto analisado não possui mensagens (por exemplo, um filtro
        que não retorna resultados), o relatório exibe uma indicação de "sem
        dados" em vez dos gráficos, sem erro (R19.4).
        """
        # R19.4: subconjunto vazio (nenhuma mensagem) → indicação "sem dados".
        resumo = stats.get("resumo") or {}
        if (resumo.get("total_mensagens") or 0) == 0:
            return StatsReportRenderer._render_empty_panel(filtro)

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
        # R26.2: o SVG do grafo é derivado exclusivamente da estrutura de dados
        # (nodes/edges) produzida pelo Statistics_Engine.
        grafo_svg = StatsReportRenderer.render_graph_svg(grafo)
        grafo_nodes = len(grafo.get("nodes") or [])
        grafo_edges = len(grafo.get("edges") or [])
        tamanho_msgs = stats["tamanho_msgs"]
        comparacao = stats["comparacao_periodos"]
        idiomas = stats["idiomas"]
        timeline = stats["timeline"]
        timeline_contatos = stats.get("timeline_contatos") or []
        atividade_noturna = stats.get("atividade_noturna") or {}
        taxa_resposta = stats.get("taxa_resposta") or []
        timeline_links = stats.get("timeline_links") or []
        dominancia_grupo = stats.get("dominancia_grupo") or []
        midia_por_contato = stats.get("midia_por_contato") or []
        velocidade_conversa = stats.get("velocidade_conversa") or []
        iniciadores = stats.get("iniciadores") or []
        rajadas = stats.get("rajadas") or []
        removidas_por_autor = stats.get("removidas_por_autor") or []

        # R22: bloco de insights automáticos no topo do relatório. Itens sem
        # dados foram omitidos pelo Statistics_Engine, portanto só renderizamos
        # o que está presente.
        filtro_banner_html = StatsReportRenderer._render_filtro_banner(filtro)
        insights_html = StatsReportRenderer._render_insights(stats.get("insights") or {})

        # Cards de resumo
        cards_html = f"""
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
        """

        # Top participantes (barras horizontais)
        max_msgs = participantes[0]["mensagens"] if participantes else 1
        participants_html = ""
        for p in participantes[:15]:
            pct = (p["mensagens"] / max_msgs) * 100
            participants_html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(p["nome"][:20])}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%"></div>
                </div>
                <div class="bar-value">{p["mensagens"]:,}</div>
            </div>"""

        # Atividade por hora
        max_hour = max((h["total"] for h in horarios["por_hora"]), default=1)
        hours_html = ""
        for h in horarios["por_hora"]:
            pct = (h["total"] / max_hour) * 100 if max_hour > 0 else 0
            hours_html += f'<div class="hour-bar" style="height:{pct}%" title="{h["hora"]}: {h["total"]} msgs"></div>'

        hour_labels = ""
        for i in range(0, 24, 3):
            hour_labels += f"<span>{i:02d}h</span>"

        # Atividade por dia da semana
        max_day = max((d["total"] for d in temporal["por_dia_semana"]), default=1)
        weekdays_html = ""
        for d in temporal["por_dia_semana"]:
            pct = (d["total"] / max_day) * 100 if max_day > 0 else 0
            weekdays_html += f"""
            <div class="weekday-item">
                <div class="weekday-bar-track">
                    <div class="weekday-bar-fill" style="height:{pct}%"></div>
                </div>
                <div class="weekday-label">{d["dia"][:3]}</div>
                <div class="weekday-value">{d["total"]:,}</div>
            </div>"""

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
            # Cores escurecidas para garantir contraste >= 4.5:1 com o fundo
            # branco das tags de palavra (R21.3): azul -> roxo -> vermelho.
            colors = [
                (30, 100, 170),  # azul escuro
                (120, 60, 200),  # roxo escuro
                (200, 40, 40),  # vermelho escuro
            ]
            for _i, w in enumerate(top_words):
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
                color = f"rgb({r},{g},{b})"
                words_html += f'<span class="word-tag" style="font-size:{size}px;color:{color}">{escape_html(w["palavra"])} <small>({w["contagem"]})</small></span> '

        # Mídias
        midias_html = f"""
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
        </div>"""

        # Chamadas
        chamadas_html = f"""
        <div class="calls-stats">
            <div class="call-stat">📞 Total: <strong>{chamadas["total"]}</strong></div>
            <div class="call-stat">✅ Atendidas: <strong>{chamadas["atendidas"]}</strong></div>
            <div class="call-stat">📵 Perdidas: <strong>{chamadas["perdidas"]}</strong></div>
            <div class="call-stat">⏱️ Duração total: <strong>{chamadas["duracao_total_formatada"]}</strong></div>
        </div>"""

        # Top conversas
        top_html = ""
        for i, c in enumerate(top):
            top_html += f"""
            <div class="top-conv-item">
                <span class="top-rank">#{i+1}</span>
                <span class="top-name">{escape_html(c["nome"][:30])}</span>
                <span class="top-msgs">{c["mensagens"]:,} msgs</span>
            </div>"""

        # Atividade mensal (últimos 12 meses ou todos)
        monthly_data = temporal["por_mes"][-24:]  # últimos 24 meses
        max_month = max((m["total"] for m in monthly_data), default=1)
        monthly_html = ""
        for m in monthly_data:
            pct = (m["total"] / max_month) * 100 if max_month > 0 else 0
            monthly_html += f"""
            <div class="month-bar-item">
                <div class="month-bar-track">
                    <div class="month-bar-fill" style="height:{pct}%"></div>
                </div>
                <div class="month-label">{m["mes"][5:]}/{m["mes"][:4]}</div>
            </div>"""

        # Tempo de resposta
        response_time_html = ""
        if tempo_resposta:
            for rt in tempo_resposta[:10]:
                response_time_html += f"""
            <div class="rt-row">
                <span class="rt-name">{escape_html(rt["nome"][:25])}</span>
                <span class="rt-stat">⏱️ Média: <strong>{rt["media_formatada"]}</strong></span>
                <span class="rt-stat">📊 Mediana: <strong>{rt["mediana_formatada"]}</strong></span>
                <span class="rt-stat">⚡ Rápida: {rt["mais_rapida"]}</span>
                <span class="rt-stat">🕔 Lenta: {rt["mais_lenta"]}</span>
                <span class="rt-count">{rt["total_respostas"]} respostas</span>
            </div>"""
        else:
            response_time_html = (
                '<div class="stats-note">Sem dados suficientes de tempo de resposta</div>'
            )

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
                # Paleta acessível em duas zonas para garantir contraste de texto
                # >= 4.5:1 (R21.3), evitando a faixa intermediária de luminância em
                # que nem texto claro nem escuro alcançam o limite:
                #  - zona clara (intensidade < 0.55): fundo claro + texto escuro;
                #  - zona escura (intensidade >= 0.55): fundo escuro + texto branco.
                if intensity == 0:
                    bg_color = "#f5f5f5"
                    text_color = "#1a1a1a"
                elif intensity < 0.55:
                    t2 = intensity / 0.55
                    r = int(245 - t2 * 95)  # 245→150
                    g = int(245 - t2 * 55)  # 245→190
                    b = int(245 - t2 * 5)  # 245→240
                    bg_color = f"rgb({r},{g},{b})"
                    text_color = "#1a1a1a"
                else:
                    t2 = (intensity - 0.55) / 0.45
                    r = int(37 + t2 * 148)  # 37→185
                    g = int(99 - t2 * 71)  # 99→28
                    b = int(235 - t2 * 207)  # 235→28
                    bg_color = f"rgb({r},{g},{b})"
                    text_color = "#fff"
                heatmap_cells += f'<div class="hm-cell" style="background:{bg_color};color:{text_color}" title="{dias_semana_hm[day_idx]} {h:02d}h: {count} msgs ({pct_of_total}%)">{count if count > 0 else ""}</div>'
        heatmap_header = '<div class="hm-label"></div>'
        for h in range(24):
            heatmap_header += f'<div class="hm-hour">{h}</div>'
        heatmap_html = f"""<div class="heatmap-container" role="img" aria-label="Mapa de calor de atividade por dia da semana e hora do dia; a contagem de mensagens é exibida em cada célula">
            <div class="hm-grid">{heatmap_header}{heatmap_cells}</div>
        </div>"""

        # Reações
        reacoes_html = ""
        if reacoes["total"] > 0:
            max_r = reacoes["por_autor"][0]["total"] if reacoes["por_autor"] else 1
            for r in reacoes["por_autor"]:
                pct = (r["total"] / max_r) * 100
                reacoes_html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(r["nome"][:20])}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%"></div>
                </div>
                <div class="bar-value">{r["total"]:,}</div>
            </div>"""
        else:
            reacoes_html = '<div class="stats-note">Nenhuma reação encontrada</div>'

        # Emojis
        emojis_cloud_html = ""
        if emojis["total_emojis"] > 0:
            for i, e in enumerate(emojis["top_30"]):
                size = max(16, 40 - i)
                emojis_cloud_html += f'<span class="emoji-tag" style="font-size:{size}px" title="{e["contagem"]}x">{escape_html(e["emoji"])} <small>{e["contagem"]}</small></span> '
            emojis_by_author_html = ""
            for ea in emojis["por_autor"][:8]:
                top3 = " ".join(escape_html(emoji) for emoji in ea["top_3"])
                emojis_by_author_html += f"""
            <div class="emoji-author-row">
                <span class="emoji-author-name">{escape_html(ea["nome"][:20])}</span>
                <span class="emoji-author-fav">{top3}</span>
                <span class="emoji-author-count">{ea["total"]:,}</span>
            </div>"""
        else:
            emojis_cloud_html = '<div class="stats-note">Nenhum emoji encontrado</div>'
            emojis_by_author_html = ""

        # Integridade de anexos
        integrity_missing_html = ""
        if integridade["faltando"] > 0:
            for m in integridade["faltando_lista"][:10]:
                integrity_missing_html += f'<div class="integrity-missing"><span>\u274c {escape_html(m["arquivo"])}</span><span class="integrity-meta">{escape_html(m["autor"])} - {escape_html(m["data"])}</span></div>'

        # Gaps de conversa
        gaps_html = ""
        if gaps["total_gaps"] > 0:
            for g in gaps["gaps"][:20]:
                gaps_html += (
                    f'<div class="gap-item">'
                    f'<span class="gap-conv">{escape_html(g["conversa"])}</span>'
                    f'<span class="gap-period">{escape_html(g["de"])} → {escape_html(g["ate"])}</span>'
                    f'<span class="gap-days">{g["dias"]} dias</span>'
                    f'</div>'
                )
        else:
            gaps_html = (
                '<div class="stats-note">Nenhum gap de inatividade ≥ 30 dias encontrado</div>'
            )

        gaps_summary = ""
        if gaps["maior_gap"]:
            gaps_summary = (
                f'<div class="stats-note">Maior gap: <strong>{gaps["maior_gap"]["dias"]} dias</strong> '
                f'em {escape_html(gaps["maior_gap"]["conversa"])} ({escape_html(gaps["maior_gap"]["de"])} → {escape_html(gaps["maior_gap"]["ate"])})'
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
                f"</div>"
            )

        # Comparação entre períodos
        comparacao_html = ""
        if comparacao.get("ativo"):
            rows_data = [
                (
                    "Mensagens",
                    comparacao["p1"]["msgs"],
                    comparacao["p2"]["msgs"],
                    comparacao["variacoes"]["msgs"],
                ),
                (
                    "Anexos",
                    comparacao["p1"]["anexos"],
                    comparacao["p2"]["anexos"],
                    comparacao["variacoes"]["anexos"],
                ),
                (
                    "Chamadas",
                    comparacao["p1"]["chamadas"],
                    comparacao["p2"]["chamadas"],
                    comparacao["variacoes"]["chamadas"],
                ),
                (
                    "Participantes",
                    comparacao["p1"]["autores"],
                    comparacao["p2"]["autores"],
                    comparacao["variacoes"]["autores"],
                ),
                (
                    "Média chars/msg",
                    comparacao["p1"]["media_len"],
                    comparacao["p2"]["media_len"],
                    comparacao["variacoes"]["media_len"],
                ),
            ]
            comparacao_rows = ""
            for label, v1, v2, var in rows_data:
                # Cores escurecidas para contraste >= 4.5:1 em fundo branco (R21.3).
                # O sinal +/- distingue a variação além da cor (R21.2).
                color = (
                    "#2e7d32"  # verde escuro (aumento)
                    if var.startswith("+")
                    else "#c62828"  # vermelho escuro (queda)
                    if var.startswith("-")
                    else "#555"  # cinza neutro (sem variação)
                )
                comparacao_rows += (
                    f"<tr><td>{escape_html(label)}</td>"
                    f'<td style="text-align:right">{v1:,}</td>'
                    f'<td style="text-align:right">{v2:,}</td>'
                    f'<td style="text-align:right;color:{color};font-weight:700">{escape_html(var)}</td></tr>'
                )
            comparacao_html = f"""
                <div class="stats-section">
                    <h3>📊 Comparação entre Períodos</h3>
                    <table class="comp-table">
                        <thead>
                            <tr>
                                <th>Métrica</th>
                                <th>1ª metade<br><small>{escape_html(comparacao["p1_de"])} → {escape_html(comparacao["p1_ate"])}</small></th>
                                <th>2ª metade<br><small>{escape_html(comparacao["p2_de"])} → {escape_html(comparacao["p2_ate"])}</small></th>
                                <th>Variação</th>
                            </tr>
                        </thead>
                        <tbody>{comparacao_rows}</tbody>
                    </table>
                </div>"""

        # Idiomas
        idiomas_html = ""
        if idiomas.get("percentuais"):
            lang_bars = ""
            for lang, pct in idiomas["percentuais"].items():
                lang_bars += (
                    f'<div class="msg-len-row">'
                    f'<span class="msg-len-label">{escape_html(lang)}</span>'
                    f'<div class="msg-len-bar-bg"><div class="msg-len-bar-fill" style="width:{pct}%"></div></div>'
                    f'<span class="msg-len-count">{pct}%</span>'
                    f"</div>"
                )
            idiomas_html = lang_bars
        else:
            idiomas_html = '<div class="stats-note">Dados insuficientes para detectar idioma</div>'

        # Timeline visual de conversas
        timeline_html = ""
        if timeline and len(timeline) >= 2:
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
                width_pct = max(
                    ((t_item["end"] - t_item["start"]).total_seconds() / total_span) * 100, 0.5
                )
                intensity = t_item["count"] / max_count if max_count > 0 else 0
                # Blue to purple gradient based on volume
                r = int(74 + intensity * 65)
                g = int(144 - intensity * 52)
                b = int(217 + intensity * 29)
                name = escape_html(t_item["name"][:25])
                start_str = t_item["start"].strftime("%d/%m/%Y")
                end_str = t_item["end"].strftime("%d/%m/%Y")
                timeline_html += (
                    f'<div class="tl-row">'
                    f'<span class="tl-name" title="{escape_html(t_item["name"])}">{name}</span>'
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

        # A1 — Timeline de contatos
        timeline_contatos_html = ""
        if timeline_contatos:
            for tc in timeline_contatos[:20]:
                timeline_contatos_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(tc["nome"][:25])}</span>'
                    f'<span class="rt-stat">📅 {tc["primeira_msg"]} → {tc["ultima_msg"]}</span>'
                    f'<span class="rt-count">{tc["total_mensagens"]:,} msgs</span>'
                    f'</div>'
                )

        # A2 — Atividade noturna
        noturna_html = ""
        noturna_total = atividade_noturna.get("total_noturna", 0)
        noturna_por_autor = atividade_noturna.get("por_autor") or []
        if noturna_por_autor:
            max_noturna = noturna_por_autor[0]["mensagens"] if noturna_por_autor else 1
            for na in noturna_por_autor[:15]:
                pct = (na["mensagens"] / max(max_noturna, 1)) * 100
                noturna_html += (
                    f'<div class="bar-row">'
                    f'<div class="bar-label">{escape_html(na["nome"][:20])}</div>'
                    f'<div class="bar-track">'
                    f'<div class="bar-fill" style="width:{pct}%"></div>'
                    f'</div>'
                    f'<div class="bar-value">{na["mensagens"]:,}</div>'
                    f'</div>'
                )

        # A4 — Taxa de resposta
        taxa_resposta_html = ""
        if taxa_resposta:
            for tr in taxa_resposta[:15]:
                taxa_resposta_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(tr["nome"][:25])}</span>'
                    f'<span class="rt-stat">🅰️ Alvo respondeu: <strong>{tr["taxa_resposta_alvo"]}%</strong></span>'
                    f'<span class="rt-stat">💬 Contato respondeu: <strong>{tr["taxa_resposta_contato"]}%</strong></span>'
                    f'<span class="rt-count">{tr["msgs_alvo"]:,} msgs alvo / {tr["msgs_contato"]:,} msgs contato</span>'
                    f'</div>'
                )
        else:
            taxa_resposta_html = (
                '<div class="stats-note">Sem dados suficientes (requer DMs com 2+ participantes)</div>'
            )

        # A8 — Timeline de links
        timeline_links_html = ""
        if timeline_links:
            for lk in timeline_links[:50]:
                timeline_links_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(lk.get("data", ""))[:16])}</span>'
                    f'<span class="rt-stat">{escape_html(str(lk.get("autor", ""))[:20])}</span>'
                    f'<span class="rt-stat">🔗 {escape_html(str(lk.get("dominio", ""))[:30])}</span>'
                    f'<span class="rt-count" title="{escape_html(str(lk.get("url", "")))}">'
                    f'{escape_html(str(lk.get("url", ""))[:40])}</span>'
                    f'</div>'
                )

        # A9 — Dominância em grupos
        dominancia_html = ""
        if dominancia_grupo:
            for dg in dominancia_grupo[:10]:
                dominancia_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(dg.get("conversa", ""))[:25])}</span>'
                    f'<span class="rt-stat">👑 {escape_html(str(dg.get("dominante", ""))[:20])} '
                    f'(<strong>{dg.get("pct_dominante", 0)}%</strong>)</span>'
                    f'<span class="rt-count">{dg.get("total_mensagens", 0):,} msgs</span>'
                    f'</div>'
                )

        # A10 — Mídia por contato
        midia_contato_html = ""
        if midia_por_contato:
            for mc in midia_por_contato[:15]:
                midia_contato_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(mc.get("nome", ""))[:20])}</span>'
                    f'<span class="rt-stat">📷 {mc.get("fotos", 0)} · 🎤 {mc.get("audios", 0)} · '
                    f'🎬 {mc.get("videos", 0)} · 🔗 {mc.get("links", 0)}</span>'
                    f'<span class="rt-count">predominante: '
                    f'{escape_html(str(mc.get("tipo_predominante", "")))}</span>'
                    f'</div>'
                )

        # A5 — Velocidade de conversa
        velocidade_html = ""
        if velocidade_conversa:
            for vc in velocidade_conversa[:15]:
                velocidade_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(vc.get("conversa", ""))[:25])}</span>'
                    f'<span class="rt-stat">⚡ pico <strong>{vc.get("msgs_por_hora_pico", 0)}</strong> msgs/h</span>'
                    f'<span class="rt-stat">média {vc.get("msgs_por_hora_media", 0)} msgs/h</span>'
                    f'<span class="rt-count">{vc.get("num_sessoes", 0)} sessões · '
                    f'{vc.get("total_msgs_ativas", 0)} msgs ativas</span>'
                    f'</div>'
                )

        # A3 — Iniciadores
        iniciadores_html = ""
        if iniciadores:
            for ini in iniciadores[:20]:
                iniciadores_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(ini.get("conversa", ""))[:25])}</span>'
                    f'<span class="rt-stat">▶️ {escape_html(str(ini.get("iniciador", ""))[:20])}</span>'
                    f'<span class="rt-stat">{escape_html(str(ini.get("data_inicio", "")))}</span>'
                    f'<span class="rt-count">{ini.get("total_mensagens", 0):,} msgs</span>'
                    f'</div>'
                )

        # A6 — Rajadas
        rajadas_html = ""
        if rajadas:
            for rj in rajadas[:15]:
                rajadas_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(rj.get("conversa", ""))[:25])}</span>'
                    f'<span class="rt-stat">🔥 maior <strong>{rj.get("maior_rajada", 0)}</strong></span>'
                    f'<span class="rt-stat">{rj.get("num_rajadas", 0)} rajadas · '
                    f'{escape_html(str(rj.get("autor_mais_rajadas", ""))[:15])}</span>'
                    f'</div>'
                )

        # A7 — Removidas por autor
        removidas_autor_html = ""
        if removidas_por_autor:
            for ra in removidas_por_autor[:15]:
                removidas_autor_html += (
                    f'<div class="rt-row">'
                    f'<span class="rt-name">{escape_html(str(ra.get("nome", ""))[:20])}</span>'
                    f'<span class="rt-stat">🗑️ <strong>{ra.get("removidas", 0)}</strong> removidas</span>'
                    f'<span class="rt-count">{ra.get("percentual", 0)}%</span>'
                    f'</div>'
                )

        investigacao_parts = [
            '<div class="stats-section">'
            "<h3>🔍 Investigação</h3>"
            '<div class="stats-note">Métricas orientadas a análise investigativa (A1–A10)</div>'
            "</div>"
        ]
        if timeline_contatos_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>📅 Timeline de Contatos (A1)</h3>"
                f'<div class="response-times">{timeline_contatos_html}</div>'
                '<div class="stats-note">Primeira e última mensagem de cada contato com o alvo • Top 20</div>'
                "</div>"
            )
        if noturna_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>🌙 Atividade Noturna (A2 — 00h–05h)</h3>"
                f'<div class="bars-container" role="img" aria-label="Mensagens noturnas por autor">{noturna_html}</div>'
                f'<div class="stats-note">Total: <strong>{noturna_total:,}</strong> mensagens noturnas</div>'
                "</div>"
            )
        if iniciadores_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>▶️ Iniciadores de Conversa (A3)</h3>"
                f'<div class="response-times">{iniciadores_html}</div>'
                '<div class="stats-note">Autor da primeira mensagem datada de cada conversa</div>'
                "</div>"
            )
        investigacao_parts.append(
            '<div class="stats-section">'
            "<h3>💬 Taxa de Resposta em DMs (A4)</h3>"
            f'<div class="response-times">{taxa_resposta_html}</div>'
            "</div>"
        )
        if velocidade_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>⚡ Velocidade de Conversa (A5)</h3>"
                f'<div class="response-times">{velocidade_html}</div>'
                '<div class="stats-note">Msgs/hora em sessões ativas (gap &lt; 30 min)</div>'
                "</div>"
            )
        if rajadas_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>� Rajadas de Mensagens (A6)</h3>"
                f'<div class="response-times">{rajadas_html}</div>'
                '<div class="stats-note">Sequências consecutivas do mesmo autor (mín. 3 msgs)</div>'
                "</div>"
            )
        if removidas_autor_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>�️ Removidas por Autor (A7)</h3>"
                f'<div class="response-times">{removidas_autor_html}</div>'
                "</div>"
            )
        if timeline_links_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>🔗 Timeline de Links (A8)</h3>"
                f'<div class="response-times">{timeline_links_html}</div>'
                '<div class="stats-note">Até 50 links, mais antigos primeiro</div>'
                "</div>"
            )
        if dominancia_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>👑 Dominância em Grupos (A9)</h3>"
                f'<div class="response-times">{dominancia_html}</div>'
                "</div>"
            )
        if midia_contato_html:
            investigacao_parts.append(
                '<div class="stats-section">'
                "<h3>📎 Mídia por Contato (A10)</h3>"
                f'<div class="response-times">{midia_contato_html}</div>'
                "</div>"
            )
        investigacao_html = "\n".join(investigacao_parts)

        return f'''
        <div class="stats-panel" id="stats-panel" style="display:none;">
            <div class="stats-container">
                <h2 class="stats-title">📊 Estatísticas das Conversas</h2>
                {filtro_banner_html}
                {insights_html}
                {investigacao_html}

                <div class="stats-section">
                    <h3>📋 Resumo Geral</h3>
                    {cards_html}
                </div>

                <div class="stats-section">
                    <h3>👥 Top Participantes</h3>
                    <div class="bars-container" role="img" aria-label="Gráfico de barras dos participantes mais ativos por número de mensagens">
                        {participants_html}
                    </div>
                </div>

                <div class="stats-row">
                    <div class="stats-section stats-half">
                        <h3>⏰ Atividade por Hora</h3>
                        <div class="hours-chart" role="img" aria-label="Gráfico de atividade por hora do dia (0 a 23 horas)">
                            {hours_html}
                        </div>
                        <div class="hours-labels">{hour_labels}</div>
                        <div class="stats-note">Hora mais ativa: <strong>{horarios["hora_mais_ativa"]}</strong></div>
                    </div>

                    <div class="stats-section stats-half">
                        <h3>📅 Atividade por Dia</h3>
                        <div class="weekdays-chart" role="img" aria-label="Gráfico de atividade por dia da semana">
                            {weekdays_html}
                        </div>
                        <div class="stats-note">Dia mais ativo: <strong>{temporal["dia_mais_ativo"]}</strong></div>
                    </div>
                </div>

                <div class="stats-section">
                    <h3>📈 Atividade Mensal</h3>
                    <div class="monthly-chart" role="img" aria-label="Gráfico de atividade mensal ao longo do tempo">
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
                    <div class="words-cloud" role="img" aria-label="Nuvem das palavras mais usadas; o tamanho e a contagem entre parênteses indicam a frequência">
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
                    <div class="tl-container" role="img" aria-label="Linha do tempo das conversas; cada barra mostra o período de atividade e o volume de mensagens">{timeline_html}</div>
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
                    <div class="bars-container" role="img" aria-label="Gráfico de barras de reações por autor">
                        {reacoes_html}
                    </div>
                    <div class="stats-note">Total: {reacoes["total"]:,} reações</div>
                </div>

                <div class="stats-section">
                    <h3>😀 Emojis Mais Usados</h3>
                    <div class="emoji-cloud" role="img" aria-label="Nuvem dos emojis mais usados; o tamanho e a contagem indicam a frequência">
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
                    {grafo_svg if grafo_svg else '<div class="stats-note">Dados insuficientes para gerar o grafo</div>'}
                    {f'<div class="stats-note">{grafo_nodes} participantes • {grafo_edges} conexões</div>' if grafo_svg else ''}
                </div>

                <div class="stats-section">
                    <h3>📏 Distribuição de Tamanho das Mensagens</h3>
                    <div class="msg-len-chart" role="img" aria-label="Gráfico de distribuição do tamanho das mensagens por faixa de caracteres">
                        {msg_length_html}
                    </div>
                    <div class="stats-note">Média: <strong>{tamanho_msgs["media_chars"]}</strong> chars/msg • {tamanho_msgs["total_msgs_com_texto"]:,} msgs com texto</div>
                </div>

                {comparacao_html}

                <div class="stats-section">
                    <h3>🌐 Idiomas Detectados</h3>
                    <div class="msg-len-chart" role="img" aria-label="Gráfico de distribuição dos idiomas detectados, em porcentagem">
                        {idiomas_html}
                    </div>
                    <div class="stats-note">Idioma principal: <strong>{escape_html(idiomas["principal"])}</strong> (detecção por palavras-chave)</div>
                </div>

            </div>
        </div>'''

    @staticmethod
    def render_graph_svg(grafo_data: dict) -> str:
        """Gera o SVG do grafo de relacionamentos a partir dos dados estruturais (R26.2).

        Recebe a estrutura produzida por ``ChatStatistics._grafo_data`` —
        ``{"nodes": [{"nome", "peso"}], "edges": [{"a", "b", "peso"}]}`` — e
        deriva exclusivamente dela a marcação SVG (layout circular, espessura
        das arestas proporcional à co-ocorrência e raio dos nós proporcional ao
        peso). Preserva a acessibilidade do grafo (R21): ``role="img"``,
        ``aria-label`` e ``<title>`` descritivos, além de rótulos em ``#444``
        sobre fundo claro para contraste >= 4.5:1 (R21.3).

        Quando não há nós ou arestas suficientes para um grafo (estrutura vazia),
        devolve uma string vazia, permitindo que o relatório exiba a indicação
        de "dados insuficientes" sem erro.
        """
        import html as html_mod
        import math

        nodes = grafo_data.get("nodes") or []
        edges = grafo_data.get("edges") or []

        if not nodes:
            return ""

        n = len(nodes)
        order = [node["nome"] for node in nodes]
        node_weights = {node["nome"]: node["peso"] for node in nodes}

        # Considerar apenas arestas cujos dois extremos são nós conhecidos.
        valid_edges = [
            e for e in edges if e.get("a") in node_weights and e.get("b") in node_weights
        ]
        if not valid_edges:
            return ""

        # Gerar posições em círculo (mesma ordem dos nós: maior peso primeiro).
        width, height = 800, 600
        cx, cy = width / 2, height / 2
        radius = min(cx, cy) - 80
        positions = {}
        for i, name in enumerate(order):
            angle = 2 * math.pi * i / n - math.pi / 2
            positions[name] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

        # Normalizar espessura das linhas
        weights = [e["peso"] for e in valid_edges]
        max_weight = max(weights)
        min_weight = min(weights)

        svg_lines = []
        for e in valid_edges:
            a, b, weight = e["a"], e["b"], e["peso"]
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
        max_node = max(node_weights[name] for name in order)
        min_node = min(node_weights[name] for name in order)

        svg_nodes = []
        for name in order:
            x, y = positions[name]
            count = node_weights[name]
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

        # role="img" + aria-label + <title> para acessibilidade do grafo (R21.1).
        # Texto dos rótulos em #444 sobre fundo claro garante contraste >= 4.5:1 (R21.3).
        aria = f"Grafo de relacionamentos com {n} participantes e {len(valid_edges)} conexões"
        svg = (
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="{html_mod.escape(aria)}" '
            f'style="width:100%;max-width:{width}px;height:auto;background:#fafafa;border-radius:12px;">'
            f"<title>{html_mod.escape(aria)}</title>"
            + "\n".join(svg_lines)
            + "\n"
            + "\n".join(svg_nodes)
            + "</svg>"
        )

        return svg

    @staticmethod
    def _render_filtro_banner(filtro: object | None) -> str:
        """Renderiza um aviso descrevendo o filtro aplicado (R19.1, R19.2).

        Retorna string vazia quando não há filtro ou ele é vazio (conjunto
        global, R19.3). Aceita ``StatsFilter`` (ou objeto com atributos
        equivalentes) ou ``dict`` com ``thread_id``/``data_inicio``/``data_fim``.
        """
        if filtro is None:
            return ""

        if isinstance(filtro, dict):
            thread_id = filtro.get("thread_id")
            data_inicio = filtro.get("data_inicio")
            data_fim = filtro.get("data_fim")
        else:
            thread_id = getattr(filtro, "thread_id", None)
            data_inicio = getattr(filtro, "data_inicio", None)
            data_fim = getattr(filtro, "data_fim", None)

        partes: list[str] = []
        if thread_id:
            partes.append(f"conversa <strong>{escape_html(str(thread_id))}</strong>")
        if data_inicio is not None or data_fim is not None:
            inicio = StatsReportRenderer._format_data(data_inicio) if data_inicio else "início"
            fim = StatsReportRenderer._format_data(data_fim) if data_fim else "fim"
            partes.append(f"período <strong>{escape_html(inicio)} → {escape_html(fim)}</strong>")

        if not partes:
            return ""

        return (
            '<div class="stats-filter-banner" role="note">'
            f'🔎 Filtro aplicado: {" • ".join(partes)}'
            "</div>"
        )

    @staticmethod
    def _format_data(valor: object) -> str:
        """Formata uma data para exibição, tolerando tipos não-datetime."""
        strftime = getattr(valor, "strftime", None)
        if callable(strftime):
            return strftime("%d/%m/%Y")
        return str(valor)

    @staticmethod
    def _render_insights(insights: dict) -> str:
        """Renderiza o bloco de insights automáticos no topo do relatório (R22).

        Cada item (picos de atividade, contato mais ativo, resposta mais rápida)
        só é exibido quando presente em ``insights``; itens ausentes (sem dados)
        são omitidos sem erro (R22.3). Quando nenhum insight está disponível,
        retorna string vazia para não poluir o relatório.
        """
        if not insights:
            return ""

        itens: list[str] = []

        picos = insights.get("picos_atividade")
        if picos:
            detalhes: list[str] = []
            if picos.get("hora"):
                detalhes.append(f"hora {escape_html(str(picos['hora']))}")
            if picos.get("dia_semana"):
                detalhes.append(f"{escape_html(str(picos['dia_semana']))}")
            mes = picos.get("mes")
            if mes:
                mes_raw = str(mes.get("mes", ""))
                rotulo = f"{mes_raw[5:]}/{mes_raw[:4]}" if len(mes_raw) >= 7 else mes_raw
                detalhes.append(f"mês {escape_html(rotulo)} ({mes.get('total', 0):,} msgs)")
            if detalhes:
                itens.append(
                    '<div class="insight-card">'
                    '<div class="insight-icon">📈</div>'
                    '<div class="insight-body">'
                    '<div class="insight-label">Picos de atividade</div>'
                    f'<div class="insight-value">{" • ".join(detalhes)}</div>'
                    "</div></div>"
                )

        contato = insights.get("contato_mais_ativo")
        if contato:
            itens.append(
                '<div class="insight-card">'
                '<div class="insight-icon">🏅</div>'
                '<div class="insight-body">'
                '<div class="insight-label">Contato mais ativo</div>'
                f'<div class="insight-value">{escape_html(str(contato.get("nome", "")))} '
                f'({contato.get("mensagens", 0):,} msgs)</div>'
                "</div></div>"
            )

        resposta = insights.get("resposta_mais_rapida")
        if resposta:
            itens.append(
                '<div class="insight-card">'
                '<div class="insight-icon">⚡</div>'
                '<div class="insight-body">'
                '<div class="insight-label">Resposta mais rápida</div>'
                f'<div class="insight-value">{escape_html(str(resposta.get("nome", "")))} '
                f'({escape_html(str(resposta.get("mediana_formatada", "")))})</div>'
                "</div></div>"
            )

        if not itens:
            return ""

        return (
            '<div class="stats-section insights-section">'
            "<h3>✨ Insights</h3>"
            f'<div class="insights-cards">{"".join(itens)}</div>'
            "</div>"
        )

    @staticmethod
    def _render_empty_panel(filtro: object | None) -> str:
        """Painel exibido quando o conjunto analisado não tem mensagens (R19.4)."""
        banner = StatsReportRenderer._render_filtro_banner(filtro)
        return f"""
        <div class="stats-panel" id="stats-panel" style="display:none;">
            <div class="stats-container">
                <h2 class="stats-title">📊 Estatísticas das Conversas</h2>
                {banner}
                <div class="stats-section">
                    <div class="stats-empty" role="status">
                        Nenhuma mensagem corresponde aos filtros selecionados.
                    </div>
                </div>
            </div>
        </div>"""

    @staticmethod
    def render_conversation_report(thread_stats: dict | None) -> str:
        """Renderiza um mini-dashboard individual para uma única conversa (R20).

        Recebe ``thread_stats``, um sub-dicionário com as métricas calculadas
        apenas para aquela conversa. Inclui participantes, volume temporal,
        tempo de resposta e mídias. Todo conteúdo dinâmico é escapado com
        ``escape_html``. O caso "sem dados" é tratado sem erro.

        Chaves esperadas (todas opcionais, com defaults seguros):
            - ``nome``: nome da conversa.
            - ``tipo``: "DM" ou "Grupo".
            - ``mensagens``: total de mensagens (int).
            - ``anexos``: total de anexos (int).
            - ``chamadas``: total de chamadas (int).
            - ``primeira_msg`` / ``ultima_msg``: datas formatadas (str).
            - ``participantes``: lista de ``{"nome", "mensagens"}`` ou um int
              com a contagem de participantes.
            - ``temporal``: dict com ``por_mes`` = lista de ``{"mes", "total"}``.
            - ``tempo_resposta``: lista de ``{"nome", "media_formatada",
              "mediana_formatada", "total_respostas"}``.
            - ``midias``: dict com ``fotos``, ``videos``, ``audios``, ``outros``.
        """
        # Caso "sem dados": dicionário ausente/vazio ou conversa sem mensagens.
        total_msgs = (thread_stats or {}).get("mensagens", 0)
        if not thread_stats or total_msgs == 0:
            return (
                '<div class="conv-report stats-section">'
                '<div class="stats-note">Sem dados para esta conversa</div>'
                "</div>"
            )

        nome = escape_html(str(thread_stats.get("nome", "Sem nome")))
        tipo = escape_html(str(thread_stats.get("tipo", "")))
        anexos = thread_stats.get("anexos", 0)
        chamadas = thread_stats.get("chamadas", 0)
        primeira = escape_html(str(thread_stats.get("primeira_msg", "N/A")))
        ultima = escape_html(str(thread_stats.get("ultima_msg", "N/A")))

        # --- Participantes -------------------------------------------------
        participantes = thread_stats.get("participantes", [])
        if isinstance(participantes, list) and participantes:
            max_p = max((p.get("mensagens", 0) for p in participantes), default=1) or 1
            participantes_html = ""
            for p in participantes[:15]:
                msgs = p.get("mensagens", 0)
                pct = (msgs / max_p) * 100 if max_p > 0 else 0
                participantes_html += f"""
            <div class="bar-row">
                <div class="bar-label">{escape_html(str(p.get("nome", ""))[:20])}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct}%"></div>
                </div>
                <div class="bar-value">{msgs:,}</div>
            </div>"""
            participantes_total = len(participantes)
        else:
            # ``participantes`` veio como contagem (int) ou vazio.
            participantes_total = participantes if isinstance(participantes, int) else 0
            participantes_html = '<div class="stats-note">Sem detalhamento de participantes</div>'

        # --- Volume temporal (mensagens por mês) ---------------------------
        temporal = thread_stats.get("temporal") or {}
        por_mes = temporal.get("por_mes", []) if isinstance(temporal, dict) else []
        if por_mes:
            meses = por_mes[-24:]  # últimos 24 meses
            max_mes = max((m.get("total", 0) for m in meses), default=1) or 1
            temporal_html = ""
            for m in meses:
                total = m.get("total", 0)
                pct = (total / max_mes) * 100 if max_mes > 0 else 0
                mes_raw = str(m.get("mes", ""))
                # Formato "YYYY-MM" → "MM/YYYY"; cai para o valor cru se diferente.
                rotulo = f"{mes_raw[5:]}/{mes_raw[:4]}" if len(mes_raw) >= 7 else mes_raw
                temporal_html += f"""
            <div class="month-bar-item">
                <div class="month-bar-track">
                    <div class="month-bar-fill" style="height:{pct}%"></div>
                </div>
                <div class="month-label">{escape_html(rotulo)}</div>
            </div>"""
        else:
            temporal_html = '<div class="stats-note">Sem dados de volume temporal</div>'

        # --- Tempo de resposta ---------------------------------------------
        tempo_resposta = thread_stats.get("tempo_resposta", [])
        if tempo_resposta:
            response_time_html = ""
            for rt in tempo_resposta[:10]:
                response_time_html += f"""
            <div class="rt-row">
                <span class="rt-name">{escape_html(str(rt.get("nome", ""))[:25])}</span>
                <span class="rt-stat">⏱️ Média: <strong>{escape_html(str(rt.get("media_formatada", "-")))}</strong></span>
                <span class="rt-stat">📊 Mediana: <strong>{escape_html(str(rt.get("mediana_formatada", "-")))}</strong></span>
                <span class="rt-count">{rt.get("total_respostas", 0)} respostas</span>
            </div>"""
        else:
            response_time_html = (
                '<div class="stats-note">Sem dados suficientes de tempo de resposta</div>'
            )

        # --- Mídias --------------------------------------------------------
        midias = thread_stats.get("midias") or {}
        midias_html = f"""
        <div class="media-stats">
            <div class="media-stat-item">
                <div class="media-stat-icon">📷</div>
                <div class="media-stat-value">{midias.get("fotos", 0)}</div>
                <div class="media-stat-label">Fotos</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">🎬</div>
                <div class="media-stat-value">{midias.get("videos", 0)}</div>
                <div class="media-stat-label">Vídeos</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">🎤</div>
                <div class="media-stat-value">{midias.get("audios", 0)}</div>
                <div class="media-stat-label">Áudios</div>
            </div>
            <div class="media-stat-item">
                <div class="media-stat-icon">📎</div>
                <div class="media-stat-value">{midias.get("outros", 0)}</div>
                <div class="media-stat-label">Outros</div>
            </div>
        </div>"""

        # Tipo é opcional; só exibe o sufixo quando presente.
        tipo_sufixo = f" • {tipo}" if tipo else ""

        return f"""
        <div class="conv-report" id="conv-report">
            <div class="stats-container">
                <h2 class="stats-title">📊 Relatório da Conversa: {nome}</h2>

                <div class="stats-section">
                    <h3>📋 Resumo</h3>
                    <div class="stats-period">
                        {primeira} → {ultima}{tipo_sufixo}
                    </div>
                    <div class="conv-summary">
                        <span class="call-stat">💬 Mensagens: <strong>{total_msgs:,}</strong></span>
                        <span class="call-stat">👥 Participantes: <strong>{participantes_total:,}</strong></span>
                        <span class="call-stat">📎 Anexos: <strong>{anexos:,}</strong></span>
                        <span class="call-stat">📞 Chamadas: <strong>{chamadas:,}</strong></span>
                    </div>
                </div>

                <div class="stats-section">
                    <h3>👥 Participantes</h3>
                    <div class="bars-container" role="img" aria-label="Gráfico de barras dos participantes da conversa por número de mensagens">
                        {participantes_html}
                    </div>
                </div>

                <div class="stats-section">
                    <h3>📈 Volume Temporal (por mês)</h3>
                    <div class="monthly-chart" role="img" aria-label="Gráfico de volume de mensagens da conversa por mês">
                        {temporal_html}
                    </div>
                </div>

                <div class="stats-section">
                    <h3>⏱️ Tempo de Resposta</h3>
                    <div class="response-times">
                        {response_time_html}
                    </div>
                </div>

                <div class="stats-section">
                    <h3>📷 Mídias</h3>
                    {midias_html}
                </div>
            </div>
        </div>"""

    @staticmethod
    def get_stats_css() -> str:
        """Retorna CSS para o painel de estatísticas"""
        return """
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

        /* Aviso de filtro aplicado (R19) */
        .stats-filter-banner {
            margin-bottom: 20px;
            padding: 10px 16px;
            background: #eef4ff;
            border: 1px solid #c7d9ff;
            border-radius: 10px;
            font-size: 13px;
            color: #2c3e66;
        }

        /* Indicação de conjunto vazio (R19.4) */
        .stats-empty {
            padding: 24px;
            text-align: center;
            font-size: 14px;
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
        }

        /* Sumário de insights automáticos (R22) */
        .insights-cards {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }

        .insight-card {
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1 1 220px;
            padding: 14px 16px;
            background: #ffffff;
            border: 1px solid #e3e3e3;
            border-radius: 10px;
        }

        .insight-icon {
            font-size: 24px;
            line-height: 1;
        }

        .insight-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
        }

        .insight-value {
            font-size: 14px;
            font-weight: 600;
            color: #333;
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
            color: #595959; /* contraste >= 4.5:1 em fundo claro (R21.3) */
            margin-top: 4px;
        }

        .stats-period {
            text-align: center;
            font-size: 12px;
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
        }

        /* Chamadas */
        .calls-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        /* Relatório por conversa */
        .conv-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 12px;
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
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
            color: #595959; /* contraste >= 4.5:1 (R21.3) */
            padding: 4px 140px 0 140px;
        }
        @media (max-width: 768px) {
            .tl-name { width: 80px; font-size: 10px; }
            .tl-axis { padding: 4px 90px 0 90px; }
        }
        """

    @staticmethod
    def get_stats_js() -> str:
        """Retorna JavaScript para o painel de estatísticas"""
        return """
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
        """
