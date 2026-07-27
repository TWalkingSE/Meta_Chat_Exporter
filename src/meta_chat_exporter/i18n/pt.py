"""
Meta Platforms Chat Exporter - Recurso de idioma: Português (pt)

Idioma padrão do projeto. Externaliza as strings de interface/estatísticas
(R36.1) e a lista de stop words (R36.2) usadas pelos cálculos analíticos.

IMPORTANTE: os valores aqui definidos são idênticos aos literais que estavam
embutidos no código, de modo que selecionar o recurso ``pt`` (padrão) preserve
exatamente o comportamento observável anterior.
"""

# Código ISO do idioma deste recurso.
LANGUAGE_CODE = "pt"

# Nome de exibição do idioma.
LANGUAGE_NAME = "Português"

# ---------------------------------------------------------------------------
# Stop words (R36.2)
# ---------------------------------------------------------------------------
# Conjunto histórico usado em ``_stats_palavras`` (combina termos comuns de
# português e inglês). Mantido idêntico para não alterar a contagem de palavras.
STOP_WORDS: set[str] = {
    "a",
    "e",
    "o",
    "de",
    "da",
    "do",
    "em",
    "que",
    "é",
    "um",
    "uma",
    "para",
    "com",
    "não",
    "no",
    "na",
    "os",
    "as",
    "se",
    "por",
    "mais",
    "eu",
    "mas",
    "me",
    "ele",
    "ela",
    "te",
    "isso",
    "esse",
    "essa",
    "este",
    "esta",
    "foi",
    "ser",
    "tem",
    "já",
    "muito",
    "como",
    "ao",
    "aos",
    "das",
    "dos",
    "ou",
    "sua",
    "seu",
    "meu",
    "minha",
    "nao",
    "ta",
    "tá",
    "vc",
    "voce",
    "pra",
    "pro",
    "só",
    "so",
    "sim",
    "aqui",
    "aí",
    "ai",
    "lá",
    "la",
    "né",
    "ne",
    "eh",
    "ah",
    "oh",
    "ok",
    "vou",
    "vai",
    "ter",
    "tudo",
    "bem",
    "dia",
    "bom",
    "boa",
    "the",
    "to",
    "and",
    "of",
    "in",
    "is",
    "it",
    "you",
    "that",
    "was",
    "for",
    "on",
    "are",
    "with",
    "this",
    "have",
    "from",
}

# ---------------------------------------------------------------------------
# Strings de interface/estatísticas (R36.1)
# ---------------------------------------------------------------------------
# Nomes dos dias da semana (usados nas estatísticas temporais).
WEEKDAY_NAMES: list[str] = [
    "Segunda",
    "Terça",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sábado",
    "Domingo",
]

# Rótulos diversos de UI/estatísticas. As chaves são estáveis (independem do
# idioma); os valores são traduzíveis por recurso.
UI_STRINGS: dict[str, str] = {
    # Genéricos
    "not_available": "N/A",
    "no_data": "Sem dados",
    "unknown": "Indeterminado",
    "no_name": "Sem nome",
    # Tipos de conversa
    "conversation_type_group": "Grupo",
    "conversation_type_dm": "DM",
    # Períodos do dia
    "period_dawn": "Madrugada",
    "period_morning": "Manhã",
    "period_afternoon": "Tarde",
    "period_night": "Noite",
    # Seções de estatísticas
    "stats_summary": "Resumo geral",
    "stats_participants": "Por participante",
    "stats_conversations": "Por conversa",
    "stats_temporal": "Temporal",
    "stats_media": "Mídias",
    "stats_calls": "Chamadas",
    "stats_words": "Palavras",
    "stats_hours": "Horários",
    "stats_response_time": "Tempo de resposta",
    "stats_heatmap": "Mapa de calor",
    "stats_reactions": "Reações",
    "stats_emojis": "Emojis",
    "stats_gaps": "Períodos de inatividade",
    "stats_languages": "Idiomas",
    "stats_edited": "Mensagens editadas",
    "stats_period_comparison": "Comparação de períodos",
}
