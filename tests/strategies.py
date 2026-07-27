"""
Estratégias Hypothesis compartilhadas para testes baseados em propriedade.

Define geradores reutilizáveis para os modelos de domínio (`Message`, `Thread`,
`ProfileMedia`, `GenericCategory` e seus auxiliares), cobrindo deliberadamente os
casos de borda exigidos pelo design:

- Caracteres especiais de HTML (`<`, `>`, `&`, aspas).
- Números longos (>= 8 dígitos) — relevantes para redação de telefones/IDs.
- Strings vazias e compostas apenas por espaços em branco.
- Datas variadas (passado/presente, com e sem horário).
- Conteúdo não-ASCII (acentos, emojis, alfabetos diversos).

Os geradores são reaproveitados pelas suítes de propriedade (Hypothesis, >= 100
iterações). Veja `design.md` — seção "Testing Strategy".
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

from hypothesis import strategies as st

# Permitir importar os módulos planos do projeto a partir de tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.models import (  # noqa: E402
    Attachment,
    GenericCategory,
    GenericRecord,
    Message,
    Participant,
    Photo,
    ProfileMedia,
    Story,
    Thread,
    Video,
)

# ---------------------------------------------------------------------------
# Estratégias de texto (incluem os casos de borda exigidos)
# ---------------------------------------------------------------------------

# Caracteres especiais de HTML que precisam de escape no relatório.
_SPECIAL_HTML = st.sampled_from(["<", ">", "&", '"', "'", "<script>", "a & b", "x < y > z"])

# Strings vazias ou apenas com espaços em branco.
_BLANK = st.sampled_from(["", " ", "   ", "\t", "\n", " \t\n "])

# Conteúdo não-ASCII: acentos, emojis e outros alfabetos.
_NON_ASCII = st.sampled_from(
    [
        "café",
        "ação",
        "naïve",
        "Müller",
        "日本語",
        "Привет",
        "emoji 😀🎉",
        "मनुष्य",
        "العربية",
    ]
)

# Texto "comum" gerado livremente, incluindo qualquer caractere unicode.
_FREE_TEXT = st.text(max_size=40)

#: Estratégia de texto geral combinando todos os casos relevantes.
text_strategy: st.SearchStrategy[str] = st.one_of(
    _FREE_TEXT,
    _BLANK,
    _SPECIAL_HTML,
    _NON_ASCII,
)


def long_number_strategy() -> st.SearchStrategy[str]:
    """Gera strings numéricas com 8 a 15 dígitos (>= 8, alvo de redação)."""
    return st.integers(min_value=10_000_000, max_value=999_999_999_999_999).map(str)


#: Texto que frequentemente embute um número longo (telefone/ID) no corpo.
text_with_long_number: st.SearchStrategy[str] = st.builds(
    lambda prefix, number, suffix: f"{prefix}{number}{suffix}",
    prefix=st.sampled_from(["", "tel: ", "ligar ", "id="]),
    number=long_number_strategy(),
    suffix=st.sampled_from(["", " agora", " <fim>", " 😀"]),
)


# ---------------------------------------------------------------------------
# Estratégias de data/hora
# ---------------------------------------------------------------------------

#: Datas variadas entre 2000 e 2035, com componentes de hora diversos.
datetime_strategy: st.SearchStrategy[datetime] = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2035, 12, 31, 23, 59, 59),
)

#: Data opcional (modelos usam `datetime | None`).
optional_datetime_strategy: st.SearchStrategy[datetime | None] = st.one_of(
    st.none(),
    datetime_strategy,
)


# ---------------------------------------------------------------------------
# Estratégias dos modelos de domínio
# ---------------------------------------------------------------------------


def participants() -> st.SearchStrategy[Participant]:
    """Gera um `Participant` (username, platform, user_id)."""
    return st.builds(
        Participant,
        username=st.one_of(text_strategy, _NON_ASCII),
        platform=st.sampled_from(["instagram", "messenger", "whatsapp", "facebook", ""]),
        user_id=st.one_of(st.just(""), long_number_strategy()),
    )


def attachments() -> st.SearchStrategy[Attachment]:
    """Gera um `Attachment` com nomes/URLs potencialmente problemáticos."""
    return st.builds(
        Attachment,
        filename=st.one_of(text_strategy, st.just("foto<1>.jpg")),
        file_type=st.sampled_from(["image", "video", "audio", "file", ""]),
        size=st.integers(min_value=0, max_value=10_000_000),
        url=st.one_of(st.just(""), text_with_long_number),
        local_path=st.one_of(st.just(""), text_strategy),
    )


def messages() -> st.SearchStrategy[Message]:
    """Gera uma `Message` cobrindo flags, anexos e conteúdo variado."""
    return st.builds(
        Message,
        author=st.one_of(text_strategy, _NON_ASCII),
        author_id=st.one_of(st.just(""), long_number_strategy()),
        platform=st.sampled_from(["instagram", "messenger", "whatsapp", "facebook", ""]),
        sent=optional_datetime_strategy,
        body=st.one_of(text_strategy, text_with_long_number),
        disappearing=st.booleans(),
        disappearing_duration=st.sampled_from(["", "24h", "7d", "1 semana"]),
        attachments=st.lists(attachments(), max_size=3),
        share_url=st.one_of(st.none(), text_with_long_number),
        share_text=st.one_of(st.none(), text_strategy),
        is_call=st.booleans(),
        call_type=st.sampled_from(["", "audio", "video"]),
        call_duration=st.integers(min_value=0, max_value=36_000),
        call_missed=st.booleans(),
        removed_by_sender=st.booleans(),
        source_file=st.one_of(st.just(""), text_strategy),
        is_reaction=st.booleans(),
        subscription_event=st.sampled_from(["", "subscribe", "unsubscribe"]),
        subscription_users=st.lists(st.one_of(text_strategy, _NON_ASCII), max_size=3),
        has_payment=st.booleans(),
        is_edited=st.booleans(),
    )


def threads() -> st.SearchStrategy[Thread]:
    """Gera uma `Thread` com participantes e mensagens."""
    return st.builds(
        Thread,
        thread_id=st.one_of(text_strategy, long_number_strategy()),
        thread_name=st.one_of(text_strategy, _NON_ASCII),
        participants=st.lists(participants(), max_size=4),
        past_participants=st.lists(participants(), max_size=2),
        messages=st.lists(messages(), max_size=5),
        ai_enabled=st.booleans(),
        read_receipts=st.sampled_from(["Enabled", "Disabled", ""]),
        base_dir=st.none(),
    )


def photos() -> st.SearchStrategy[Photo]:
    """Gera uma `Photo`."""
    return st.builds(
        Photo,
        photo_id=st.one_of(text_strategy, long_number_strategy()),
        taken=optional_datetime_strategy,
        caption=st.one_of(text_strategy, _NON_ASCII),
        owner=st.one_of(text_strategy, _NON_ASCII),
        privacy=st.sampled_from(["", "public", "private", "friends"]),
        local_path=st.one_of(st.just(""), text_strategy),
        url=st.one_of(st.just(""), text_with_long_number),
        like_count=st.integers(min_value=0, max_value=1_000_000),
        location_name=st.one_of(st.just(""), text_strategy),
        location_address=st.one_of(st.just(""), text_strategy),
        carousel_id=st.one_of(st.just(""), text_strategy),
        filter_name=st.one_of(st.just(""), text_strategy),
        is_published=st.sampled_from(["", "true", "false"]),
        source=st.one_of(st.just(""), text_strategy),
        source_file=st.one_of(st.just(""), text_strategy),
        category=st.one_of(st.just(""), text_strategy),
    )


def videos() -> st.SearchStrategy[Video]:
    """Gera um `Video`."""
    return st.builds(
        Video,
        video_id=st.one_of(text_strategy, long_number_strategy()),
        taken=optional_datetime_strategy,
        caption=st.one_of(text_strategy, _NON_ASCII),
        owner=st.one_of(text_strategy, _NON_ASCII),
        privacy=st.sampled_from(["", "public", "private", "friends"]),
        local_path=st.one_of(st.just(""), text_strategy),
        url=st.one_of(st.just(""), text_with_long_number),
        like_count=st.integers(min_value=0, max_value=1_000_000),
        location_name=st.one_of(st.just(""), text_strategy),
        location_address=st.one_of(st.just(""), text_strategy),
        carousel_id=st.one_of(st.just(""), text_strategy),
        filter_name=st.one_of(st.just(""), text_strategy),
        is_published=st.sampled_from(["", "true", "false"]),
        source=st.one_of(st.just(""), text_strategy),
        source_file=st.one_of(st.just(""), text_strategy),
        category=st.one_of(st.just(""), text_strategy),
    )


def stories() -> st.SearchStrategy[Story]:
    """Gera um `Story`."""
    return st.builds(
        Story,
        story_id=st.one_of(text_strategy, long_number_strategy()),
        time=optional_datetime_strategy,
        owner=st.one_of(text_strategy, _NON_ASCII),
        privacy=st.sampled_from(["", "public", "private", "friends"]),
        local_path=st.one_of(st.just(""), text_strategy),
        media_type=st.sampled_from(["image", "video", ""]),
        ai_generated=st.booleans(),
        source_file=st.one_of(st.just(""), text_strategy),
        category=st.one_of(st.just(""), text_strategy),
    )


def generic_records() -> st.SearchStrategy[GenericRecord]:
    """Gera um `GenericRecord` (lista de dicionários chave/valor)."""
    entry = st.dictionaries(
        keys=st.one_of(text_strategy, _NON_ASCII).filter(lambda s: s != ""),
        values=st.one_of(text_strategy, text_with_long_number, _NON_ASCII),
        max_size=4,
    )
    return st.builds(GenericRecord, entries=st.lists(entry, max_size=4))


def generic_categories() -> st.SearchStrategy[GenericCategory]:
    """Gera uma `GenericCategory` com registros genéricos."""
    return st.builds(
        GenericCategory,
        category_id=st.one_of(text_strategy, long_number_strategy()),
        category_name=st.one_of(text_strategy, _NON_ASCII),
        records=st.lists(generic_records(), max_size=4),
    )


def profile_medias() -> st.SearchStrategy[ProfileMedia]:
    """Gera um `ProfileMedia` com mídias e categorias genéricas."""
    return st.builds(
        ProfileMedia,
        photos=st.lists(photos(), max_size=3),
        videos=st.lists(videos(), max_size=3),
        stories=st.lists(stories(), max_size=3),
        generic_categories=st.lists(generic_categories(), max_size=3),
    )
