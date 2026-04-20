"""
Testes para o módulo parser.py - Parser HTML de registros Meta
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import MetaRecordsParser
from models import Thread, Message, Attachment, Participant
import constants


class TestParserInit(unittest.TestCase):
    """Testes de inicialização do parser"""

    def test_init_with_nonexistent_file(self):
        p = MetaRecordsParser("nonexistent_file.html")
        self.assertEqual(p.threads, [])
        self.assertEqual(p.owner_username, "")
        self.assertEqual(p.owner_id, "")

    def test_init_sets_paths(self):
        p = MetaRecordsParser("test_file.html")
        self.assertEqual(p.source_filename, "test_file.html")

    def test_parse_nonexistent_file_returns_empty(self):
        p = MetaRecordsParser("does_not_exist.html")
        result = p.parse()
        self.assertEqual(result, [])


class TestParserWithHTML(unittest.TestCase):
    """Testes de parsing com HTML sintético"""

    def _create_temp_html(self, content: str, filename: str = "test_parse.html") -> str:
        """Cria arquivo HTML temporário para testes"""
        path = Path(__file__).parent / filename
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(path)

    def _cleanup(self, filename: str = "test_parse.html"):
        path = Path(__file__).parent / filename
        if path.exists():
            path.unlink()

    def setUp(self):
        # Fixar timezone para testes
        constants.set_timezone_offset(timedelta(hours=-3))

    def tearDown(self):
        self._cleanup()

    def test_parse_empty_file(self):
        path = self._create_temp_html("")
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(result, [])
        self.assertEqual(p.owner_username, "")

    def test_parse_no_unified_messages(self):
        html = '<html><body><div>No messages here</div></body></html>'
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(result, [])

    def test_extract_owner_info(self):
        html = '''<html><body>
        <div class="t">Account Identifier<div class="m"><div>testuser123</div></div></div>
        <div class="t">Target<div class="m"><div>9876543210</div></div></div>
        <div id="property-unified_messages">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        p.parse()
        self.assertEqual(p.owner_username, "testuser123")
        self.assertEqual(p.owner_id, "9876543210")

    def test_parse_single_thread_with_message(self):
        html = '''<html><body>
        <div class="t">Account Identifier<div class="m"><div>owner</div></div></div>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (12345678)
        Current Participants<div class="m"><div>user1 (instagram: 100), user2 (instagram: 200)</div></div>
        <div class="t o">Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-01-15 13:30:00 UTC</div></div>
        Body<div class="m"><div>Hello World!</div></div><div class="p"></div></div>
        </div>
        <div id="property-other_section">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(len(result), 1)
        thread = result[0]
        self.assertEqual(thread.thread_id, "12345678")
        self.assertEqual(len(thread.participants), 2)
        self.assertEqual(len(thread.messages), 1)
        msg = thread.messages[0]
        self.assertEqual(msg.author, "user1")
        self.assertEqual(msg.author_id, "100")
        self.assertEqual(msg.body, "Hello World!")
        # UTC -3 = 10:30
        self.assertEqual(msg.sent.hour, 10)
        self.assertEqual(msg.sent.minute, 30)

    def test_parse_disappearing_message(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (99999999)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-06-01 12:00:00 UTC</div></div>
        Body<div class="m"><div>Temporary msg</div></div>
        Disappearing Message<div class="m"><div>On</div></div>
        Disappearing Duration<div class="m"><div>24 hours</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(len(result), 1)
        msg = result[0].messages[0]
        self.assertTrue(msg.disappearing)
        self.assertEqual(msg.disappearing_duration, "24 hours")

    def test_parse_call_record(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (11111111)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-03-01 08:00:00 UTC</div></div>
        Body<div class="m"><div>Started a call</div></div>
        Call Record
        Type<div class="m"><div>Video</div></div>
        Duration<div class="m"><div>300</div></div>
        Missed<div class="m"><div>false</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertTrue(msg.is_call)
        self.assertEqual(msg.call_type, "Video")
        self.assertEqual(msg.call_duration, 300)
        self.assertFalse(msg.call_missed)

    def test_parse_missed_call(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (22222222)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-03-01 08:00:00 UTC</div></div>
        Body<div class="m"><div>Missed call</div></div>
        Call Record
        Type<div class="m"><div>Audio</div></div>
        Duration<div class="m"><div>0</div></div>
        Missed<div class="m"><div>true</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertTrue(msg.is_call)
        self.assertTrue(msg.call_missed)

    def test_parse_attachment(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (33333333)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-02-01 10:00:00 UTC</div></div>
        Body<div class="m"><div>Check this photo</div></div>
        Linked Media File:<div class="m"><div>photos/image001.jpg</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertEqual(len(msg.attachments), 1)
        self.assertEqual(msg.attachments[0].filename, "image001.jpg")
        self.assertIn("image", msg.attachments[0].file_type)

    def test_parse_share(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (44444444)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-04-01 14:00:00 UTC</div></div>
        Body<div class="m"><div>Look at this</div></div>
        Share<div class="m">
        Url<div class="m"><div>https://example.com/post</div></div>
        Text<div class="m"><div>Cool post!</div></div>
        </div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertEqual(msg.share_url, "https://example.com/post")
        self.assertEqual(msg.share_text, "Cool post!")

    def test_parse_multiple_messages_sorted(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (55555555)
        Current Participants<div class="m"><div>user1 (instagram: 100), user2 (instagram: 200)</div></div>
        Author<div class="m"><div>user2 (instagram: 200)</div></div>
        Sent<div class="m"><div>2024-01-15 16:00:00 UTC</div></div>
        Body<div class="m"><div>Second message</div></div><div class="p"></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-01-15 15:00:00 UTC</div></div>
        Body<div class="m"><div>First message</div></div><div class="p"></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(len(result[0].messages), 2)
        # Messages should be sorted by time
        self.assertEqual(result[0].messages[0].body, "First message")
        self.assertEqual(result[0].messages[1].body, "Second message")

    def test_parse_payment_detection(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (66666666)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-05-01 09:00:00 UTC</div></div>
        Body<div class="m"><div>A payment request was auto-detected.</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertTrue(msg.has_payment)

    def test_parse_reaction_detection(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (77777777)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-05-01 10:00:00 UTC</div></div>
        Body<div class="m"><div>Liked a message</div></div><div class="p"></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertTrue(msg.is_reaction)

    def test_parse_removed_by_sender(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (88888888)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-05-01 10:00:00 UTC</div></div>
        Body<div class="m"><div>Message content</div></div>
        Removed by Sender
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        msg = result[0].messages[0]
        self.assertTrue(msg.removed_by_sender)

    def test_source_file_set(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (11112222)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-01-01 00:00:00 UTC</div></div>
        Body<div class="m"><div>test</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(result[0].messages[0].source_file, "test_parse.html")

    def test_parse_ai_enabled(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (99990000)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        AI<div class="m"><div>true</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-01-01 00:00:00 UTC</div></div>
        Body<div class="m"><div>AI test</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertTrue(result[0].ai_enabled)

    def test_parse_thread_name(self):
        html = '''<html><body>
        <div id="property-unified_messages">
        Thread<div class="m"><div>Conversa (11110000)
        Current Participants<div class="m"><div>user1 (instagram: 100)</div></div>
        Thread Name<div class="m"><div>Meu Grupo Legal</div></div>
        Author<div class="m"><div>user1 (instagram: 100)</div></div>
        Sent<div class="m"><div>2024-01-01 00:00:00 UTC</div></div>
        Body<div class="m"><div>group test</div></div>
        </div>
        <div id="property-end">
        </div>
        </body></html>'''
        path = self._create_temp_html(html)
        p = MetaRecordsParser(path)
        result = p.parse()
        self.assertEqual(result[0].thread_name, "Meu Grupo Legal")


class TestReadFileSafe(unittest.TestCase):
    """Testes para leitura de arquivo com fallback de encoding"""

    def test_read_utf8(self):
        path = Path(__file__).parent / "test_encoding.html"
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<html>Olá Açúcar Ñ</html>')
        p = MetaRecordsParser(str(path))
        content = p._read_file_safe()
        self.assertIn("Açúcar", content)
        path.unlink()

    def test_read_latin1(self):
        path = Path(__file__).parent / "test_latin.html"
        with open(path, 'wb') as f:
            f.write('Olá Açúcar'.encode('latin-1'))
        p = MetaRecordsParser(str(path))
        content = p._read_file_safe()
        self.assertIsNotNone(content)
        path.unlink()

    def test_empty_file(self):
        path = Path(__file__).parent / "test_empty.html"
        path.touch()
        p = MetaRecordsParser(str(path))
        result = p.parse()
        self.assertEqual(result, [])
        path.unlink()


if __name__ == "__main__":
    unittest.main()
