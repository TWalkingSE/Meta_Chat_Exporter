"""
Testes para o módulo exporters.py - Exportadores JSON e CSV
"""

import sys
import os
import json
import csv
import unittest
from datetime import datetime
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Thread, Message, Attachment, Participant
from exporters import JSONExporter, CSVExporter


def _make_msg(author="user1", body="Hello", sent=None, attachments=None,
              is_call=False, call_type="", call_duration=0, call_missed=False,
              disappearing=False, share_url=None, share_text=None,
              removed_by_sender=False):
    return Message(
        author=author,
        author_id="100",
        platform="instagram",
        sent=sent or datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        disappearing=disappearing,
        disappearing_duration="",
        attachments=attachments or [],
        share_url=share_url,
        share_text=share_text,
        is_call=is_call,
        call_type=call_type,
        call_duration=call_duration,
        call_missed=call_missed,
        removed_by_sender=removed_by_sender,
        source_file="test.html",
    )


def _make_thread(thread_id="1", name="Test Chat", participants=None, messages=None):
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=participants or [Participant("user1", "instagram", "100"),
                                       Participant("user2", "instagram", "200")],
        messages=messages or [],
    )


class TestJSONExporter(unittest.TestCase):
    """Testes para exportação JSON"""

    def setUp(self):
        self.output_path = Path(__file__).parent / "test_output.json"

    def tearDown(self):
        if self.output_path.exists():
            self.output_path.unlink()

    def test_export_basic(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=False)

        self.assertTrue(self.output_path.exists())
        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn("meta", data)
        self.assertIn("conversas", data)
        self.assertEqual(data["meta"]["total_conversas"], 1)
        self.assertEqual(data["meta"]["total_mensagens"], 2)
        self.assertEqual(data["meta"]["owner_username"], "user1")

    def test_export_with_stats(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=True)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn("estatisticas", data)
        self.assertIn("resumo", data["estatisticas"])

    def test_export_message_fields(self):
        msg = _make_msg(body="Test message", share_url="https://example.com",
                        share_text="Cool link")
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertEqual(conv_msg["corpo"], "Test message")
        self.assertEqual(conv_msg["link_compartilhado"], "https://example.com")

    def test_export_call_message(self):
        msg = _make_msg(is_call=True, call_type="Video", call_duration=120, call_missed=False)
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertIn("chamada", conv_msg)
        self.assertEqual(conv_msg["chamada"]["tipo"], "Video")
        self.assertEqual(conv_msg["chamada"]["duracao"], 120)

    def test_export_disappearing_message(self):
        msg = _make_msg(disappearing=True)
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertTrue(conv_msg["temporaria"])

    def test_export_attachment(self):
        att = Attachment(filename="photo.jpg", file_type="image/jpeg")
        msg = _make_msg(attachments=[att])
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertIn("anexos", conv_msg)
        self.assertEqual(conv_msg["anexos"][0]["filename"], "photo.jpg")

    def test_export_empty_threads(self):
        exporter = JSONExporter([], "user1", "100")
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertEqual(data["meta"]["total_conversas"], 0)
        self.assertEqual(data["conversas"], [])


class TestCSVExporter(unittest.TestCase):
    """Testes para exportação CSV"""

    def setUp(self):
        self.output_path = Path(__file__).parent / "test_output.csv"
        self.stats_path = Path(__file__).parent / "test_output_stats.csv"

    def tearDown(self):
        for p in [self.output_path, self.stats_path]:
            if p.exists():
                p.unlink()

    def test_export_basic(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = CSVExporter([thread], "user1", "100")
        exporter.export(self.output_path)

        self.assertTrue(self.output_path.exists())
        with open(self.output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["autor"], "user1")
        self.assertEqual(rows[0]["corpo"], "Hello")

    def test_csv_fields(self):
        msg = _make_msg(disappearing=True, share_url="https://ex.com",
                        is_call=True, call_type="Audio")
        thread = _make_thread(messages=[msg])
        exporter = CSVExporter([thread])
        exporter.export(self.output_path)

        with open(self.output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

        self.assertEqual(row["temporaria"], "Sim")
        self.assertEqual(row["eh_chamada"], "Sim")
        self.assertEqual(row["tipo_chamada"], "Audio")
        self.assertEqual(row["link_compartilhado"], "https://ex.com")

    def test_export_stats(self):
        msgs = [_make_msg(), _make_msg(author="user2")]
        thread = _make_thread(messages=msgs)
        exporter = CSVExporter([thread], "user1", "100")
        exporter.export(self.output_path)
        exporter.export_stats(self.stats_path)

        self.assertTrue(self.stats_path.exists())

    def test_multiple_threads(self):
        t1 = _make_thread(thread_id="1", messages=[_make_msg(body="A")])
        t2 = _make_thread(thread_id="2", name="Chat 2", messages=[_make_msg(body="B")])
        exporter = CSVExporter([t1, t2])
        exporter.export(self.output_path)

        with open(self.output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        thread_ids = {r["conversa_id"] for r in rows}
        self.assertEqual(thread_ids, {"1", "2"})

    def test_attachment_in_csv(self):
        att = Attachment(filename="voice.m4a", file_type="audio/mp4")
        msg = _make_msg(attachments=[att])
        thread = _make_thread(messages=[msg])
        exporter = CSVExporter([thread])
        exporter.export(self.output_path)

        with open(self.output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)

        self.assertEqual(row["anexos"], "voice.m4a")
        self.assertEqual(row["tipos_anexo"], "audio/mp4")


if __name__ == "__main__":
    unittest.main()
