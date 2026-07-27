"""
Testes para o módulo safe_cache.py - Serialização JSON segura do cache
"""

import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.models import (
    Attachment,
    Message,
    Participant,
    Photo,
    ProfileMedia,
    Story,
    Thread,
    Video,
)
from meta_chat_exporter.safe_cache import CACHE_VERSION, load_cache, save_cache
from tests.strategies import messages, profile_medias, threads


def _make_thread() -> Thread:
    msg = Message(
        author="alice",
        author_id="100",
        platform="instagram",
        sent=datetime(2024, 3, 1, 12, 30, 0),
        body="Olá mundo",
        attachments=[Attachment(filename="foto.jpg", file_type="image", size=1234)],
        is_call=False,
    )
    call = Message(
        author="bob",
        author_id="200",
        platform="instagram",
        sent=datetime(2024, 3, 1, 12, 35, 0),
        body="",
        is_call=True,
        call_type="video",
        call_duration=42,
    )
    return Thread(
        thread_id="t1",
        thread_name="Conversa",
        participants=[
            Participant("alice", "instagram", "100"),
            Participant("bob", "instagram", "200"),
        ],
        messages=[msg, call],
    )


class TestSafeCacheRoundtrip(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_thread_roundtrip(self):
        thread = _make_thread()
        save_cache(self.path, {"threads": [thread]})
        loaded = load_cache(self.path)

        self.assertIsNotNone(loaded)
        restored = loaded["threads"][0]
        self.assertIsInstance(restored, Thread)
        self.assertEqual(restored.thread_id, "t1")
        self.assertEqual(restored.thread_name, "Conversa")
        self.assertEqual(len(restored.messages), 2)

    def test_message_fields_preserved(self):
        thread = _make_thread()
        save_cache(self.path, {"threads": [thread]})
        restored = load_cache(self.path)["threads"][0]

        msg = restored.messages[0]
        self.assertIsInstance(msg, Message)
        self.assertEqual(msg.author, "alice")
        self.assertEqual(msg.body, "Olá mundo")
        self.assertIsInstance(msg.sent, datetime)
        self.assertEqual(msg.sent, datetime(2024, 3, 1, 12, 30, 0))

    def test_attachment_preserved(self):
        thread = _make_thread()
        save_cache(self.path, {"threads": [thread]})
        restored = load_cache(self.path)["threads"][0]

        att = restored.messages[0].attachments[0]
        self.assertIsInstance(att, Attachment)
        self.assertEqual(att.filename, "foto.jpg")
        self.assertEqual(att.size, 1234)

    def test_participant_preserved(self):
        thread = _make_thread()
        save_cache(self.path, {"threads": [thread]})
        restored = load_cache(self.path)["threads"][0]

        p = restored.participants[0]
        self.assertIsInstance(p, Participant)
        self.assertEqual(p.username, "alice")
        self.assertEqual(p.user_id, "100")

    def test_call_message_preserved(self):
        thread = _make_thread()
        save_cache(self.path, {"threads": [thread]})
        restored = load_cache(self.path)["threads"][0]

        call = restored.messages[1]
        self.assertTrue(call.is_call)
        self.assertEqual(call.call_type, "video")
        self.assertEqual(call.call_duration, 42)


class TestSafeCacheMedia(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "media.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_profile_media_roundtrip(self):
        pm = ProfileMedia(
            photos=[Photo(photo_id="p1", taken=datetime(2024, 1, 1), caption="legenda")],
            videos=[Video(video_id="v1", taken=datetime(2024, 1, 2))],
            stories=[Story(story_id="s1", time=datetime(2024, 1, 3), media_type="image")],
        )
        save_cache(self.path, {"media": pm})
        loaded = load_cache(self.path)["media"]

        self.assertIsInstance(loaded, ProfileMedia)
        self.assertIsInstance(loaded.photos[0], Photo)
        self.assertEqual(loaded.photos[0].caption, "legenda")
        self.assertIsInstance(loaded.videos[0], Video)
        self.assertIsInstance(loaded.stories[0], Story)
        self.assertEqual(loaded.stories[0].media_type, "image")

    def test_path_roundtrip(self):
        save_cache(self.path, {"dir": Path("some/dir")})
        loaded = load_cache(self.path)
        self.assertIsInstance(loaded["dir"], Path)
        self.assertEqual(loaded["dir"], Path("some/dir"))


class TestSafeCacheSecurity(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_corrupted_cache_returns_none(self):
        self.path.write_text("not valid json {{{", encoding="utf-8")
        self.assertIsNone(load_cache(self.path))

    def test_missing_file_returns_none(self):
        missing = Path(self._tmp.name) / "missing.json"
        self.assertIsNone(load_cache(missing))

    def test_unknown_marker_is_ignored_not_executed(self):
        # Marcador desconhecido não deve ser convertido em objeto
        payload = {
            "cache_version": CACHE_VERSION,
            "data": {"value": {"__evil__": "payload", "data": 1}},
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_cache(self.path)
        self.assertEqual(loaded["value"], {"__evil__": "payload", "data": 1})


# Feature: melhorias-analise-e-projeto, Property 1: Round-trip de cache preserva todos os campos
@settings(max_examples=100)
@given(
    msgs=st.lists(messages(), max_size=4),
    thrs=st.lists(threads(), max_size=3),
    media=profile_medias(),
)
def test_property_cache_roundtrip_preserva_todos_os_campos(msgs, thrs, media):
    """Para qualquer Message ou ProfileMedia válido (incluindo is_edited e
    generic_categories), serializar com save_cache e desserializar com load_cache
    deve produzir um objeto equivalente em todos os campos.

    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """
    data = {"messages": msgs, "threads": thrs, "media": media}

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"
        save_cache(path, data)
        loaded = load_cache(path)

    assert loaded is not None

    # Mensagens: igualdade de dataclass cobre todos os campos, incluindo is_edited.
    assert loaded["messages"] == msgs
    for original, restored in zip(msgs, loaded["messages"], strict=False):
        assert isinstance(restored, Message)
        assert restored.is_edited == original.is_edited

    # Threads (com mensagens e participantes aninhados).
    assert loaded["threads"] == thrs

    # ProfileMedia: igualdade de dataclass cobre generic_categories e seus records.
    restored_media = loaded["media"]
    assert isinstance(restored_media, ProfileMedia)
    assert restored_media == media
    assert restored_media.generic_categories == media.generic_categories


# Feature: melhorias-analise-e-projeto, Property 2: Cache com versão incompatível é descartado
@settings(max_examples=100)
@given(
    versao=st.one_of(
        st.integers().filter(lambda v: v != CACHE_VERSION),
        st.text(),
        st.none(),
        st.floats(allow_nan=False, allow_infinity=False).filter(lambda v: v != CACHE_VERSION),
        st.booleans(),
    ),
    incluir_versao=st.booleans(),
)
def test_property_versao_incompativel_descarta_cache(versao, incluir_versao):
    """Para qualquer arquivo de cache cuja `cache_version` difira da versão
    corrente (incluindo o caso em que a chave está ausente), load_cache deve
    retornar None (ausência de dados).

    Validates: Requirements 2.1, 2.2, 2.3
    """
    payload: dict = {"data": {"value": 1}}
    if incluir_versao:
        payload["cache_version"] = versao

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "cache.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_cache(path)

    assert loaded is None


if __name__ == "__main__":
    unittest.main()
