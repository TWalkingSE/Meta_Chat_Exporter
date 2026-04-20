"""
Testes para os regex pré-compilados em constants.py
"""

import sys
import os
import unittest

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    RE_THREAD, RE_ACCOUNT_ID, RE_TARGET, RE_PARTICIPANTS,
    RE_USERNAME, RE_AI_STATUS, RE_THREAD_NAME, RE_AUTHOR, RE_SENT,
    RE_BODY, RE_DISAPPEARING, RE_DISAPPEARING_DURATION, RE_LINKED_MEDIA,
    RE_SHARE_URL, RE_SHARE_TEXT, RE_CALL_TYPE, RE_CALL_DURATION,
    RE_CALL_MISSED, RE_PAGE_BREAK_FULL, RE_SUBSCRIPTION_TYPE,
    RE_SUBSCRIPTION_USERS, RE_PAST_PARTICIPANTS, RE_READ_RECEIPTS,
    RE_PAYMENT, RE_HTML_TAGS, RE_PAGE_BREAK, RE_MULTIPLE_SPACES,
    TRANSLATIONS, TRANSLATIONS_KEYS_SORTED,
    get_timezone_offset, set_timezone_offset
)
from datetime import timedelta


class TestThreadRegex(unittest.TestCase):
    """Testes para RE_THREAD"""

    def test_basic_match(self):
        text = 'Thread<div class="m"><div>Conversa (12345678)'
        match = RE_THREAD.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "12345678")

    def test_long_id(self):
        text = 'Thread<div class="m"><div>Chat (9876543210123)'
        match = RE_THREAD.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "9876543210123")

    def test_no_match(self):
        text = 'Random text without thread marker'
        match = RE_THREAD.search(text)
        self.assertIsNone(match)


class TestAccountIdRegex(unittest.TestCase):
    """Testes para RE_ACCOUNT_ID"""

    def test_basic_match(self):
        text = 'Account Identifier<div class="m"><div>testuser123'
        match = RE_ACCOUNT_ID.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "testuser123")


class TestTargetRegex(unittest.TestCase):
    """Testes para RE_TARGET"""

    def test_basic_match(self):
        text = 'Target<div class="m"><div>9876543210'
        match = RE_TARGET.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "9876543210")


class TestUsernameRegex(unittest.TestCase):
    """Testes para RE_USERNAME"""

    def test_basic_match(self):
        text = 'john_doe (instagram: 12345)'
        matches = RE_USERNAME.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], ('john_doe', 'instagram', '12345'))

    def test_multiple_users(self):
        text = 'user1 (instagram: 100), user2 (facebook: 200)'
        matches = RE_USERNAME.findall(text)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0][0], 'user1')
        self.assertEqual(matches[1][0], 'user2')

    def test_username_with_dots(self):
        text = 'user.name.test (instagram: 100)'
        matches = RE_USERNAME.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], 'user.name.test')


class TestAuthorRegex(unittest.TestCase):
    """Testes para RE_AUTHOR"""

    def test_basic_match(self):
        text = 'Author<div class="m"><div>john_doe (instagram: 12345)'
        match = RE_AUTHOR.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).strip(), 'john_doe')
        self.assertEqual(match.group(2).strip(), 'instagram')
        self.assertEqual(match.group(3).strip(), '12345')


class TestSentRegex(unittest.TestCase):
    """Testes para RE_SENT"""

    def test_basic_match(self):
        text = 'Sent<div class="m"><div>2024-01-15 13:30:00 UTC'
        match = RE_SENT.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), '2024-01-15 13:30:00 UTC')

    def test_no_match_without_utc(self):
        text = 'Sent<div class="m"><div>2024-01-15 13:30:00'
        match = RE_SENT.search(text)
        self.assertIsNone(match)


class TestBodyRegex(unittest.TestCase):
    """Testes para RE_BODY"""

    def test_basic_match(self):
        text = 'Body<div class="m"><div>Hello World<div class="p">'
        match = RE_BODY.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Hello World')


class TestDisappearingRegex(unittest.TestCase):
    """Testes para RE_DISAPPEARING"""

    def test_on(self):
        text = 'Disappearing Message<div class="m"><div>On'
        match = RE_DISAPPEARING.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'On')

    def test_off(self):
        text = 'Disappearing Message<div class="m"><div>Off'
        match = RE_DISAPPEARING.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Off')


class TestLinkedMediaRegex(unittest.TestCase):
    """Testes para RE_LINKED_MEDIA"""

    def test_basic_match(self):
        text = 'Linked Media File:<div class="m"><div>photos/image001.jpg'
        matches = RE_LINKED_MEDIA.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0], 'photos/image001.jpg')


class TestShareRegex(unittest.TestCase):
    """Testes para RE_SHARE_URL e RE_SHARE_TEXT"""

    def test_url_match(self):
        text = 'Url<div class="m"><div>https://example.com/post'
        match = RE_SHARE_URL.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'https://example.com/post')

    def test_text_match(self):
        text = 'Text<div class="m"><div>Cool post!'
        match = RE_SHARE_TEXT.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Cool post!')


class TestCallRegex(unittest.TestCase):
    """Testes para regex de chamadas"""

    def test_call_type(self):
        text = 'Type<div class="m"><div>Video'
        match = RE_CALL_TYPE.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Video')

    def test_call_duration(self):
        text = 'Duration<div class="m"><div>300'
        match = RE_CALL_DURATION.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), '300')

    def test_call_missed_true(self):
        text = 'Missed<div class="m"><div>true'
        match = RE_CALL_MISSED.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).lower(), 'true')

    def test_call_missed_false(self):
        text = 'Missed<div class="m"><div>false'
        match = RE_CALL_MISSED.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).lower(), 'false')


class TestSubscriptionRegex(unittest.TestCase):
    """Testes para regex de subscription events"""

    def test_subscribe(self):
        text = 'Subscription Event stuff Type<div class="m"><div>subscribe'
        match = RE_SUBSCRIPTION_TYPE.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'subscribe')

    def test_unsubscribe(self):
        text = 'Subscription Event stuff Type<div class="m"><div>unsubscribe'
        match = RE_SUBSCRIPTION_TYPE.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'unsubscribe')


class TestPaymentRegex(unittest.TestCase):
    """Testes para RE_PAYMENT"""

    def test_match(self):
        text = 'A payment request was auto-detected.'
        match = RE_PAYMENT.search(text)
        self.assertIsNotNone(match)

    def test_case_insensitive(self):
        text = 'PAYMENT REQUEST WAS AUTO-DETECTED'
        match = RE_PAYMENT.search(text)
        self.assertIsNotNone(match)


class TestReadReceiptsRegex(unittest.TestCase):
    """Testes para RE_READ_RECEIPTS"""

    def test_enabled(self):
        text = 'Read Receipts<div class="m"><div>Enabled'
        match = RE_READ_RECEIPTS.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Enabled')

    def test_disabled(self):
        text = 'Read Receipts<div class="m"><div>Disabled'
        match = RE_READ_RECEIPTS.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Disabled')


class TestPageBreakFullRegex(unittest.TestCase):
    """Testes para RE_PAGE_BREAK_FULL"""

    def test_basic_match(self):
        text = '</div><div id="page_42" class="pageBreak">Meta Platforms Business Record Page 42</div><div>'
        result = RE_PAGE_BREAK_FULL.sub('', text)
        self.assertNotIn('pageBreak', result)
        self.assertNotIn('Meta Platforms Business Record Page', result)


class TestCleaningRegex(unittest.TestCase):
    """Testes para regex de limpeza"""

    def test_html_tags_removal(self):
        text = '<div class="test">Hello</div>'
        result = RE_HTML_TAGS.sub('', text)
        self.assertEqual(result, 'Hello')

    def test_page_break_removal(self):
        text = 'Hello Meta Platforms Business Record Page 42 World'
        result = RE_PAGE_BREAK.sub('', text)
        self.assertNotIn('Meta Platforms Business Record Page', result)

    def test_multiple_spaces(self):
        text = 'Hello    World'
        result = RE_MULTIPLE_SPACES.sub(' ', text)
        self.assertEqual(result, 'Hello World')


class TestAIStatusRegex(unittest.TestCase):
    """Testes para RE_AI_STATUS"""

    def test_true(self):
        text = 'AI<div class="m"><div>true'
        match = RE_AI_STATUS.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).lower(), 'true')

    def test_false(self):
        text = 'AI<div class="m"><div>false'
        match = RE_AI_STATUS.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).lower(), 'false')

    def test_case_insensitive(self):
        text = 'AI<div class="m"><div>True'
        match = RE_AI_STATUS.search(text)
        self.assertIsNotNone(match)


class TestTranslations(unittest.TestCase):
    """Testes para a estrutura de traduções"""

    def test_translations_not_empty(self):
        self.assertGreater(len(TRANSLATIONS), 0)

    def test_sorted_keys_descending(self):
        """Verifica que chaves estão ordenadas por comprimento decrescente"""
        for i in range(len(TRANSLATIONS_KEYS_SORTED) - 1):
            self.assertGreaterEqual(
                len(TRANSLATIONS_KEYS_SORTED[i]),
                len(TRANSLATIONS_KEYS_SORTED[i + 1])
            )

    def test_all_keys_in_sorted(self):
        self.assertEqual(set(TRANSLATIONS_KEYS_SORTED), set(TRANSLATIONS.keys()))


class TestTimezoneThreadSafe(unittest.TestCase):
    """Testes para funções de timezone thread-safe"""

    def test_get_default(self):
        offset = get_timezone_offset()
        self.assertIsInstance(offset, timedelta)

    def test_set_and_get(self):
        original = get_timezone_offset()
        try:
            set_timezone_offset(timedelta(hours=5))
            self.assertEqual(get_timezone_offset(), timedelta(hours=5))
        finally:
            set_timezone_offset(original)

    def test_set_negative(self):
        original = get_timezone_offset()
        try:
            set_timezone_offset(timedelta(hours=-5))
            self.assertEqual(get_timezone_offset(), timedelta(hours=-5))
        finally:
            set_timezone_offset(original)


if __name__ == "__main__":
    unittest.main()
