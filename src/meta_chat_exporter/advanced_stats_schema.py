"""
Meta Platforms Chat Exporter - Esquema compartilhado das métricas avançadas

Este módulo define a fonte única de verdade para a exportação das métricas
avançadas (R7–R18, R22, R26). Tanto o `JSONExporter` (seção
`estatisticas.avancadas`) quanto o `CSVExporter` (`export_advanced_stats`,
tarefa 29.2) importam este esquema para garantir nomes de campos consistentes
entre os formatos (Requirement 29.3).

Cada família de métrica avançada é descrita por um :class:`AdvancedStatsFamily`:

- ``source_key``: chave da família no dicionário retornado por
  ``ChatStatistics.generate_all()``. É por esta chave que os exportadores
  recuperam os dados já calculados (e já redigidos na Data_Layer).
- ``json_key``: nome da subseção dentro de ``estatisticas.avancadas`` no JSON.
- ``rotulo``: rótulo legível em português para uso em relatórios/CSV.
- ``campos``: nomes de campos/colunas estáveis usados pela família. São os
  mesmos nomes que JSON e CSV devem empregar, garantindo consistência.

Observação importante para tarefas relacionadas: vários métodos ``_stats_*`` em
``stats.py`` (editadas, domínios, iniciativa, sessões, streaks, n-gramas, etc.)
são implementados em outras tarefas. Os exportadores recuperam cada família de
forma defensiva (``dict.get``), portanto famílias ainda não implementadas
simplesmente não aparecem na saída, sem causar erro. À medida que esses métodos
forem implementados, eles devem registrar seus resultados em ``generate_all()``
sob a ``source_key`` correspondente declarada aqui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdvancedStatsFamily:
    """Descreve uma família de métrica avançada para exportação JSON/CSV."""

    source_key: str
    json_key: str
    rotulo: str
    campos: tuple[str, ...]


# Fonte única de verdade das famílias de métricas avançadas (R7–R18, R22, R26).
# A ordem define a ordem de apresentação na seção `estatisticas.avancadas`.
ADVANCED_STATS_FAMILIES: tuple[AdvancedStatsFamily, ...] = (
    # R7 - Estatísticas de mensagens editadas
    AdvancedStatsFamily(
        source_key="editadas",
        json_key="editadas",
        rotulo="Mensagens editadas",
        campos=("total", "por_autor", "nome"),
    ),
    # R8 - Pagamentos ao longo do tempo
    AdvancedStatsFamily(
        source_key="pagamentos",
        json_key="pagamentos",
        rotulo="Pagamentos",
        campos=("total", "por_periodo", "periodo", "contagem"),
    ),
    # R8 - Eventos de grupo ao longo do tempo
    AdvancedStatsFamily(
        source_key="eventos_grupo",
        json_key="eventos_grupo",
        rotulo="Eventos de grupo",
        campos=("total", "por_periodo", "periodo", "contagem"),
    ),
    # R9 - Mensagens removidas (temporal)
    AdvancedStatsFamily(
        source_key="removidas_temporal",
        json_key="removidas_temporal",
        rotulo="Mensagens removidas (temporal)",
        campos=("total", "por_periodo", "periodo", "contagem"),
    ),
    # R9 - Mensagens temporárias (temporal)
    AdvancedStatsFamily(
        source_key="temporarias_temporal",
        json_key="temporarias_temporal",
        rotulo="Mensagens temporárias (temporal)",
        campos=("total", "por_periodo", "periodo", "contagem"),
    ),
    # R10 - Domínios de links compartilhados
    AdvancedStatsFamily(
        source_key="dominios",
        json_key="dominios",
        rotulo="Domínios de links",
        campos=("total", "por_dominio", "dominio", "contagem"),
    ),
    # R11 - Indicador de iniciativa (inícios/encerramentos)
    AdvancedStatsFamily(
        source_key="iniciativa",
        json_key="iniciativa",
        rotulo="Iniciativa",
        campos=(
            "total_inicios",
            "total_encerramentos",
            "por_autor",
            "nome",
            "inicios",
            "encerramentos",
        ),
    ),
    # R12 - Índice de reciprocidade por DM
    AdvancedStatsFamily(
        source_key="reciprocidade",
        json_key="reciprocidade",
        rotulo="Reciprocidade (DM)",
        campos=("thread_id", "indice_msgs", "indice_chars"),
    ),
    # R13 - Sessões de conversa
    AdvancedStatsFamily(
        source_key="sessoes",
        json_key="sessoes",
        rotulo="Sessões de conversa",
        campos=("thread_id", "num_sessoes", "duracao_media_segundos"),
    ),
    # R14 - Evolução do contato / esfriamento
    AdvancedStatsFamily(
        source_key="esfriamento",
        json_key="esfriamento",
        rotulo="Esfriamento",
        campos=("thread_id", "serie_temporal", "em_esfriamento"),
    ),
    # R15 - Streaks de dias consecutivos
    AdvancedStatsFamily(
        source_key="streaks",
        json_key="streaks",
        rotulo="Streaks",
        campos=("thread_id", "maior_streak_dias", "inicio", "fim"),
    ),
    # R16 - Bigramas e trigramas
    AdvancedStatsFamily(
        source_key="ngramas",
        json_key="ngramas",
        rotulo="N-gramas",
        campos=("bigramas", "trigramas", "ngrama", "contagem"),
    ),
    # R17 - Métricas linguísticas por participante
    AdvancedStatsFamily(
        source_key="linguistico",
        json_key="linguistico",
        rotulo="Métricas linguísticas",
        campos=(
            "nome",
            "razao_pergunta_afirmacao",
            "riqueza_vocabulario",
            "distribuicao_horaria",
            "perfil_horario",
        ),
    ),
    # R18 - Análise de sentimento offline (opcional)
    AdvancedStatsFamily(
        source_key="sentimento",
        json_key="sentimento",
        rotulo="Sentimento",
        campos=("nome", "distribuicao_tom"),
    ),
    # R22 - Sumário de insights automáticos
    AdvancedStatsFamily(
        source_key="insights",
        json_key="insights",
        rotulo="Insights",
        campos=("picos_atividade", "contato_mais_ativo", "resposta_mais_rapida"),
    ),
    # R26 - Dados do grafo de relacionamentos (estrutura, sem SVG)
    AdvancedStatsFamily(
        source_key="grafo",
        json_key="grafo",
        rotulo="Grafo de relacionamentos",
        campos=("nodes", "edges", "nome", "peso", "a", "b"),
    ),
    # A1 - Timeline de contatos (primeira/última mensagem com o alvo)
    AdvancedStatsFamily(
        source_key="timeline_contatos",
        json_key="timeline_contatos",
        rotulo="Timeline de contatos",
        campos=("nome", "primeira_msg", "ultima_msg", "total_mensagens"),
    ),
    # A2 - Atividade noturna (00h–05h)
    AdvancedStatsFamily(
        source_key="atividade_noturna",
        json_key="atividade_noturna",
        rotulo="Atividade noturna",
        campos=("total_noturna", "por_autor", "nome", "mensagens"),
    ),
    # A4 - Taxa de resposta em DMs
    AdvancedStatsFamily(
        source_key="taxa_resposta",
        json_key="taxa_resposta",
        rotulo="Taxa de resposta (DM)",
        campos=(
            "nome",
            "msgs_alvo",
            "msgs_contato",
            "respostas_alvo",
            "respostas_contato",
            "taxa_resposta_alvo",
            "taxa_resposta_contato",
        ),
    ),
    # A8 - Timeline de links compartilhados
    AdvancedStatsFamily(
        source_key="timeline_links",
        json_key="timeline_links",
        rotulo="Timeline de links",
        campos=("data", "autor", "url", "dominio", "conversa"),
    ),
    # A9 - Dominância em grupos
    AdvancedStatsFamily(
        source_key="dominancia_grupo",
        json_key="dominancia_grupo",
        rotulo="Dominância em grupos",
        campos=(
            "conversa",
            "thread_id",
            "total_mensagens",
            "participantes",
            "dominante",
            "pct_dominante",
            "nome",
            "mensagens",
            "percentual",
        ),
    ),
    # A10 - Padrão de mídia por contato
    AdvancedStatsFamily(
        source_key="midia_por_contato",
        json_key="midia_por_contato",
        rotulo="Mídia por contato",
        campos=(
            "nome",
            "fotos",
            "audios",
            "videos",
            "links",
            "total_midia",
            "tipo_predominante",
        ),
    ),
    # A5 - Velocidade de conversa (msgs/hora em sessões ativas)
    AdvancedStatsFamily(
        source_key="velocidade_conversa",
        json_key="velocidade_conversa",
        rotulo="Velocidade de conversa",
        campos=(
            "conversa",
            "thread_id",
            "num_sessoes",
            "msgs_por_hora_media",
            "msgs_por_hora_pico",
            "total_msgs_ativas",
        ),
    ),
    # A3 - Iniciadores de conversa
    AdvancedStatsFamily(
        source_key="iniciadores",
        json_key="iniciadores",
        rotulo="Iniciadores de conversa",
        campos=("conversa", "thread_id", "iniciador", "data_inicio", "total_mensagens"),
    ),
    # A6 - Rajadas de mensagens
    AdvancedStatsFamily(
        source_key="rajadas",
        json_key="rajadas",
        rotulo="Rajadas de mensagens",
        campos=(
            "conversa",
            "thread_id",
            "num_rajadas",
            "maior_rajada",
            "autor_mais_rajadas",
        ),
    ),
    # A7 - Removidas por autor
    AdvancedStatsFamily(
        source_key="removidas_por_autor",
        json_key="removidas_por_autor",
        rotulo="Removidas por autor",
        campos=("nome", "removidas", "percentual"),
    ),
)


# Índice por chave de origem para lookup rápido (reutilizado por JSON e CSV).
ADVANCED_STATS_BY_SOURCE_KEY: dict[str, AdvancedStatsFamily] = {
    fam.source_key: fam for fam in ADVANCED_STATS_FAMILIES
}


def build_advanced_section(stats: dict[str, Any]) -> dict[str, Any]:
    """Monta a subseção ``avancadas`` a partir do dicionário de estatísticas.

    Recupera cada família declarada em :data:`ADVANCED_STATS_FAMILIES` de forma
    defensiva: famílias ausentes em ``stats`` (ainda não implementadas) são
    simplesmente omitidas, sem causar erro. Os dados já vêm calculados e
    redigidos da Data_Layer, portanto nenhuma transformação adicional é feita.

    Args:
        stats: dicionário retornado por ``ChatStatistics.generate_all()``.

    Returns:
        Dicionário ``{json_key: dados}`` contendo apenas as famílias presentes.
    """
    avancadas: dict[str, Any] = {}
    for family in ADVANCED_STATS_FAMILIES:
        valor = stats.get(family.source_key)
        if valor is not None:
            avancadas[family.json_key] = valor
    return avancadas
