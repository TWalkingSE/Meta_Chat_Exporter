"""
Meta Platforms Chat Exporter - Language resource: English (en)

Recurso de exemplo demonstrando a tradução das strings de interface/estatísticas
(R36.1) e da lista de stop words (R36.2). Selecionar este recurso apresenta as
strings de UI em inglês (R36.3).
"""

# ISO code of this language resource.
LANGUAGE_CODE = "en"

# Display name of the language.
LANGUAGE_NAME = "English"

# ---------------------------------------------------------------------------
# Stop words (R36.2)
# ---------------------------------------------------------------------------
STOP_WORDS: set[str] = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "from",
    "by",
    "is",
    "it",
    "be",
    "was",
    "were",
    "are",
    "this",
    "that",
    "these",
    "those",
    "you",
    "your",
    "i",
    "me",
    "my",
    "we",
    "he",
    "she",
    "her",
    "his",
    "they",
    "them",
    "have",
    "has",
    "had",
    "do",
    "did",
    "not",
    "no",
    "yes",
    "so",
    "just",
    "ok",
    "okay",
    "yeah",
    "like",
    "what",
    "when",
    "who",
    "how",
    "more",
    "about",
    "know",
    "think",
    "right",
}

# ---------------------------------------------------------------------------
# UI/statistics strings (R36.1)
# ---------------------------------------------------------------------------
WEEKDAY_NAMES: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

UI_STRINGS: dict[str, str] = {
    # Generic
    "not_available": "N/A",
    "no_data": "No data",
    "unknown": "Unknown",
    "no_name": "No name",
    # Conversation types
    "conversation_type_group": "Group",
    "conversation_type_dm": "DM",
    # Time periods
    "period_dawn": "Dawn",
    "period_morning": "Morning",
    "period_afternoon": "Afternoon",
    "period_night": "Night",
    # Statistics sections
    "stats_summary": "Overview",
    "stats_participants": "By participant",
    "stats_conversations": "By conversation",
    "stats_temporal": "Temporal",
    "stats_media": "Media",
    "stats_calls": "Calls",
    "stats_words": "Words",
    "stats_hours": "Hours",
    "stats_response_time": "Response time",
    "stats_heatmap": "Heatmap",
    "stats_reactions": "Reactions",
    "stats_emojis": "Emojis",
    "stats_gaps": "Inactivity gaps",
    "stats_languages": "Languages",
    "stats_edited": "Edited messages",
    "stats_period_comparison": "Period comparison",
}
