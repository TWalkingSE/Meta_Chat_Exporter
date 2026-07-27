"""
Meta Platforms Chat Exporter - Internacionalização (i18n)

Mecanismo leve de recursos de idioma (R36). Externaliza em módulos de recurso
(``i18n/pt.py``, ``i18n/en.py``) as strings de interface/estatísticas (R36.1) e
a lista de stop words (R36.2), além das listas de detecção de idioma em
``i18n/detection.py`` (R36.2). Permite selecionar um recurso de idioma e obter
as strings/listas correspondentes (R36.3), com ``pt`` como padrão para preservar
o comportamento atual.

Uso típico::

    from meta_chat_exporter.i18n import get_stop_words, get_weekday_names, set_language, get_string

    set_language("en")          # seleciona o recurso de idioma
    get_string("stats_summary")  # -> "Overview"

As funções aceitam um parâmetro ``lang`` opcional para obter recursos de um
idioma específico sem alterar o idioma global selecionado.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from meta_chat_exporter.i18n import detection

# Idioma padrão: preserva o comportamento histórico (português).
DEFAULT_LANGUAGE = "pt"

# Idiomas com recurso disponível.
_AVAILABLE_LANGUAGES: tuple[str, ...] = ("pt", "en")

# Idioma de interface atualmente selecionado.
_current_language = DEFAULT_LANGUAGE

# Cache de módulos de recurso já carregados.
_resource_cache: dict[str, ModuleType] = {}


def available_languages() -> tuple[str, ...]:
    """Retorna os códigos de idioma com recurso disponível."""
    return _AVAILABLE_LANGUAGES


def _normalize_language(lang: str | None) -> str:
    """Normaliza o código de idioma, recorrendo ao padrão quando inválido."""
    if not lang:
        return _current_language
    lang = lang.lower()
    if lang not in _AVAILABLE_LANGUAGES:
        return DEFAULT_LANGUAGE
    return lang


def _load_resource(lang: str) -> ModuleType:
    """Carrega (com cache) o módulo de recurso do idioma informado."""
    if lang not in _resource_cache:
        try:
            module = importlib.import_module(f"meta_chat_exporter.i18n.{lang}")
        except ModuleNotFoundError:
            module = importlib.import_module(f"meta_chat_exporter.i18n.{DEFAULT_LANGUAGE}")
        _resource_cache[lang] = module
    return _resource_cache[lang]


def set_language(lang: str) -> None:
    """Seleciona o idioma de interface. Valores inválidos caem no padrão."""
    global _current_language
    _current_language = _normalize_language(lang)


def get_language() -> str:
    """Retorna o código do idioma de interface selecionado."""
    return _current_language


def get_resource(lang: str | None = None) -> ModuleType:
    """Retorna o módulo de recurso do idioma informado (ou o selecionado)."""
    return _load_resource(_normalize_language(lang))


def get_strings(lang: str | None = None) -> dict[str, str]:
    """Retorna uma cópia do dicionário de strings de UI do idioma."""
    return dict(get_resource(lang).UI_STRINGS)


def get_string(key: str, lang: str | None = None, default: str | None = None) -> str:
    """Retorna a string de UI associada a ``key`` no idioma selecionado.

    Recorre ao recurso padrão quando a chave não existe no idioma escolhido e,
    por fim, à própria ``key`` (ou a ``default``) quando ausente em ambos.
    """
    strings = get_resource(lang).UI_STRINGS
    if key in strings:
        return strings[key]
    fallback = get_resource(DEFAULT_LANGUAGE).UI_STRINGS
    if key in fallback:
        return fallback[key]
    return key if default is None else default


def get_weekday_names(lang: str | None = None) -> list[str]:
    """Retorna a lista de nomes dos dias da semana do idioma."""
    return list(get_resource(lang).WEEKDAY_NAMES)


def get_stop_words(lang: str | None = None) -> set[str]:
    """Retorna o conjunto de stop words do idioma (R36.2)."""
    return set(get_resource(lang).STOP_WORDS)


def get_lang_keywords() -> dict[str, set[str]]:
    """Retorna o mapa de palavras-chave por idioma para detecção (R36.2)."""
    return {lang: set(words) for lang, words in detection.LANG_KEYWORDS.items()}


def get_lang_code_map() -> dict[str, str]:
    """Retorna o mapa de código ISO -> nome de exibição de idioma (R36.2)."""
    return dict(detection.LANG_CODE_MAP)


__all__: list[str] = [
    "DEFAULT_LANGUAGE",
    "available_languages",
    "set_language",
    "get_language",
    "get_resource",
    "get_strings",
    "get_string",
    "get_weekday_names",
    "get_stop_words",
    "get_lang_keywords",
    "get_lang_code_map",
]
