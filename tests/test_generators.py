"""
Testes para os geradores HTML com escrita em stream.
"""

import sys
import os
import unittest
from datetime import datetime
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generators_single import ChatHTMLGenerator
from generators_all import AllChatsHTMLGenerator
from models import (
    Attachment,
    GenericCategory,
    GenericRecord,
    Message,
    Participant,
    Photo,
    ProfileMedia,
    Thread,
)


def _make_msg(author="user1", author_id="100", body="Hello", sent=None, attachments=None):
    return Message(
        author=author,
        author_id=author_id,
        platform="instagram",
        sent=sent or datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        disappearing=False,
        disappearing_duration="",
        attachments=attachments or [],
        share_url=None,
        share_text=None,
        is_call=False,
        call_type="",
        call_duration=0,
        call_missed=False,
        removed_by_sender=False,
        source_file="test.html",
        is_reaction=False,
        subscription_event="",
        subscription_users=[],
        has_payment=False,
        is_edited=False,
    )


def _make_thread(thread_id="1", name="Teste", messages=None):
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=[
            Participant("owner", "instagram", "100"),
            Participant("friend", "instagram", "200"),
        ],
        messages=messages or [],
    )


class TestStreamedHTMLGenerators(unittest.TestCase):
    def setUp(self):
        self.single_output = Path(__file__).parent / "test_single_stream.html"
        self.all_output = Path(__file__).parent / "test_all_stream.html"

    def tearDown(self):
        for output_path in (self.single_output, self.all_output):
            if output_path.exists():
                output_path.unlink()

    def test_single_chat_write_to_file(self):
        thread = _make_thread(messages=[
            _make_msg(author="owner", author_id="100", body="Olá"),
            _make_msg(author="friend", author_id="200", body="Tudo bem?"),
        ])
        generator = ChatHTMLGenerator(thread, "owner", "100")

        generator.write_to_file(self.single_output)

        self.assertTrue(self.single_output.exists())
        content = self.single_output.read_text(encoding="utf-8")
        self.assertIn("Tudo bem?", content)
        self.assertIn("Meta Chat Exporter", content)

    def test_all_chats_write_to_file(self):
        thread = _make_thread(messages=[
            _make_msg(author="owner", author_id="100", body="Mensagem 1"),
            _make_msg(author="friend", author_id="200", body="Mensagem 2"),
        ])
        generator = AllChatsHTMLGenerator([thread], "owner", "100")

        generator.write_to_file(self.all_output)

        self.assertTrue(self.all_output.exists())
        content = self.all_output.read_text(encoding="utf-8")
        self.assertIn("Mensagem 1", content)
        self.assertIn("Mensagem 2", content)
        self.assertIn("Meta Chat Exporter", content)

    def test_all_chats_streams_global_panels(self):
        attachment = Attachment(
            filename="imagem_teste.jpg",
            file_type="image/jpeg",
            local_path="linked_media/imagem_teste.jpg",
        )
        thread = _make_thread(messages=[
            _make_msg(
                author="friend",
                author_id="200",
                body="Com anexo",
                attachments=[attachment],
            ),
        ])
        profile_media = ProfileMedia(
            photos=[
                Photo(
                    photo_id="photo-1",
                    taken=datetime(2024, 1, 16, 15, 30, 0),
                    privacy="public",
                    local_path="profile_media/foto_perfil.jpg",
                    source="profile",
                    category="perfil",
                )
            ],
            generic_categories=[
                GenericCategory(
                    category_id="cat-1",
                    category_name="Informações Gerais",
                    records=[GenericRecord(entries=[{"Chave": "Valor teste"}])],
                )
            ],
        )
        generator = AllChatsHTMLGenerator([thread], "owner", "100", profile_media=profile_media)

        generator.write_to_file(self.all_output)

        content = self.all_output.read_text(encoding="utf-8")
        self.assertIn("global-media-gallery", content)
        self.assertIn("imagem_teste.jpg", content)
        self.assertIn("Mídias do Perfil", content)
        self.assertIn("foto_perfil.jpg", content)
        self.assertIn("Outras Categorias", content)
        self.assertIn("Valor teste", content)


if __name__ == "__main__":
    unittest.main()