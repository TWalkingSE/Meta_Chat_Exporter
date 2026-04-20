"""
Testes para o módulo consolidation.py - Consolidação de threads
"""

import sys
import os
import unittest
from datetime import datetime
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Thread, Message, Attachment, Participant
from consolidation import consolidate_threads, get_message_signature


def _make_msg(author="user1", author_id="100", body="Hello", sent=None,
              attachments=None, is_call=False, share_url=None,
              source_file="file1.html"):
    return Message(
        author=author,
        author_id=author_id,
        platform="instagram",
        sent=sent or datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        disappearing=False,
        disappearing_duration="",
        attachments=attachments or [],
        share_url=share_url,
        share_text=None,
        is_call=is_call,
        call_type="",
        call_duration=0,
        call_missed=False,
        removed_by_sender=False,
        source_file=source_file,
    )


def _make_thread(thread_id="1", name="", participants=None, messages=None,
                 base_dir=None):
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=participants or [Participant("user1", "instagram", "100"),
                                       Participant("user2", "instagram", "200")],
        messages=messages or [],
        base_dir=base_dir,
    )


class TestGetMessageSignature(unittest.TestCase):
    """Testes para geração de assinatura de mensagem"""

    def test_same_message_same_signature(self):
        msg1 = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0))
        msg2 = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0))
        self.assertEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_different_body_different_signature(self):
        msg1 = _make_msg(body="Hello")
        msg2 = _make_msg(body="World")
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_different_time_different_signature(self):
        msg1 = _make_msg(sent=datetime(2024, 1, 1, 10, 0))
        msg2 = _make_msg(sent=datetime(2024, 1, 1, 11, 0))
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_different_author_different_signature(self):
        msg1 = _make_msg(author_id="100")
        msg2 = _make_msg(author_id="200")
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_no_date_handled(self):
        msg = _make_msg()
        msg.sent = None  # Override after creation to bypass default
        sig = get_message_signature(msg)
        self.assertIn("no_date", sig)

    def test_body_hashed_fully(self):
        long_body = "A" * 200
        msg = _make_msg(body=long_body)
        sig = get_message_signature(msg)
        # Body in signature is now a full MD5 hash (not truncated)
        self.assertEqual(len(sig[2]), 32)  # MD5 hex digest length
        # Same body = same hash
        msg2 = _make_msg(body=long_body)
        self.assertEqual(sig[2], get_message_signature(msg2)[2])
        # Different body = different hash
        msg3 = _make_msg(body="A" * 199 + "B")
        self.assertNotEqual(sig[2], get_message_signature(msg3)[2])

    def test_attachments_in_signature(self):
        att = Attachment(filename="photo.jpg", file_type="image/jpeg")
        msg1 = _make_msg(attachments=[att])
        msg2 = _make_msg(attachments=[])
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_call_in_signature(self):
        msg1 = _make_msg(is_call=True)
        msg2 = _make_msg(is_call=False)
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))

    def test_share_url_in_signature(self):
        msg1 = _make_msg(share_url="https://example.com")
        msg2 = _make_msg(share_url=None)
        self.assertNotEqual(get_message_signature(msg1), get_message_signature(msg2))


class TestConsolidateThreads(unittest.TestCase):
    """Testes para consolidação de threads"""

    def test_no_duplicates(self):
        t1 = _make_thread(thread_id="1", messages=[_make_msg(body="A")])
        t2 = _make_thread(thread_id="2", messages=[_make_msg(body="B")])
        result = consolidate_threads([t1, t2])
        self.assertEqual(len(result), 2)

    def test_merge_same_thread_id(self):
        msg1 = _make_msg(body="A", sent=datetime(2024, 1, 1, 10, 0))
        msg2 = _make_msg(body="B", sent=datetime(2024, 1, 1, 11, 0))
        t1 = _make_thread(thread_id="1", messages=[msg1])
        t2 = _make_thread(thread_id="1", messages=[msg2])
        result = consolidate_threads([t1, t2])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].messages), 2)

    def test_deduplication(self):
        msg = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0))
        msg_dup = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0))
        t1 = _make_thread(thread_id="1", messages=[msg])
        t2 = _make_thread(thread_id="1", messages=[msg_dup])
        result = consolidate_threads([t1, t2])
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].messages), 1)

    def test_merge_participants(self):
        t1 = _make_thread(thread_id="1",
                          participants=[Participant("user1", "ig", "100")],
                          messages=[_make_msg()])
        t2 = _make_thread(thread_id="1",
                          participants=[Participant("user2", "ig", "200")],
                          messages=[_make_msg(body="different")])
        result = consolidate_threads([t1, t2])
        self.assertEqual(len(result[0].participants), 2)

    def test_thread_name_preserved(self):
        t1 = _make_thread(thread_id="1", name="", messages=[_make_msg()])
        t2 = _make_thread(thread_id="1", name="Chat Name",
                          messages=[_make_msg(body="B")])
        result = consolidate_threads([t1, t2])
        self.assertEqual(result[0].thread_name, "Chat Name")

    def test_thread_name_not_overwritten(self):
        t1 = _make_thread(thread_id="1", name="Original Name",
                          messages=[_make_msg()])
        t2 = _make_thread(thread_id="1", name="New Name",
                          messages=[_make_msg(body="B")])
        result = consolidate_threads([t1, t2])
        self.assertEqual(result[0].thread_name, "Original Name")

    def test_messages_sorted_chronologically(self):
        msg1 = _make_msg(body="First", sent=datetime(2024, 1, 1, 12, 0))
        msg2 = _make_msg(body="Second", sent=datetime(2024, 1, 1, 10, 0))
        t1 = _make_thread(thread_id="1", messages=[msg1])
        t2 = _make_thread(thread_id="1", messages=[msg2])
        result = consolidate_threads([t1, t2])
        self.assertEqual(result[0].messages[0].body, "Second")
        self.assertEqual(result[0].messages[1].body, "First")

    def test_empty_input(self):
        result = consolidate_threads([])
        self.assertEqual(result, [])

    def test_single_thread(self):
        t = _make_thread(messages=[_make_msg()])
        result = consolidate_threads([t])
        self.assertEqual(len(result), 1)

    def test_base_dir_updated(self):
        t1 = _make_thread(thread_id="1", messages=[_make_msg()], base_dir=None)
        t2 = _make_thread(thread_id="1", messages=[_make_msg(body="B")],
                          base_dir=Path("/some/dir"))
        result = consolidate_threads([t1, t2])
        self.assertEqual(result[0].base_dir, Path("/some/dir"))

    def test_records_source_prioritized(self):
        msg1 = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0),
                         source_file="some_file.html")
        msg2 = _make_msg(body="Hello", sent=datetime(2024, 1, 1, 10, 0),
                         source_file="records.html")
        t1 = _make_thread(thread_id="1", messages=[msg1])
        t2 = _make_thread(thread_id="1", messages=[msg2])
        result = consolidate_threads([t1, t2])
        self.assertEqual(result[0].messages[0].source_file, "records.html")

    def test_log_callback_called(self):
        logs = []
        t1 = _make_thread(thread_id="1", messages=[_make_msg()])
        t2 = _make_thread(thread_id="1", messages=[_make_msg(body="B")])
        consolidate_threads([t1, t2], log_callback=logs.append)
        self.assertTrue(any("Origens" in log for log in logs))

    def test_past_participants_merged(self):
        t1 = _make_thread(thread_id="1", messages=[_make_msg()])
        t1.past_participants = [Participant("old_user1", "ig", "300")]
        t2 = _make_thread(thread_id="1", messages=[_make_msg(body="B")])
        t2.past_participants = [Participant("old_user2", "ig", "400")]
        result = consolidate_threads([t1, t2])
        self.assertEqual(len(result[0].past_participants), 2)


if __name__ == "__main__":
    unittest.main()
