"""
Testes para o módulo generic_parser.py - Parser de categorias genéricas
"""

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.generic_parser import IGNORE_CATEGORIES, GenericCategoryParser


def _write_html(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return path


class TestFormatCategoryName(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = _write_html(Path(self._tmp.name), "records.html", "")
        self.parser = GenericCategoryParser(str(self.path))

    def tearDown(self):
        self._tmp.cleanup()

    def test_snake_case_to_title(self):
        self.assertEqual(
            self.parser._format_category_name("request_parameters"), "Request Parameters"
        )

    def test_single_word(self):
        self.assertEqual(self.parser._format_category_name("devices"), "Devices")


class TestKeyValueExtraction(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = _write_html(Path(self._tmp.name), "records.html", "")
        self.parser = GenericCategoryParser(str(self.path))

    def tearDown(self):
        self._tmp.cleanup()

    def test_simple_pair(self):
        chunk = 'IP Address<div class="m"><div>192.168.0.1</div>'
        record = self.parser._extract_key_value_pairs(chunk)
        self.assertEqual(record.get("IP Address"), "192.168.0.1")

    def test_html_entities_unescaped(self):
        chunk = 'Name&amp;Co<div class="m"><div>Value &gt; 5</div>'
        record = self.parser._extract_key_value_pairs(chunk)
        self.assertIn("Name&Co", record)
        self.assertEqual(record["Name&Co"], "Value > 5")

    def test_overly_long_key_rejected(self):
        long_key = "x" * 90
        chunk = f'{long_key}<div class="m"><div>val</div>'
        record = self.parser._extract_key_value_pairs(chunk)
        self.assertNotIn(long_key, record)

    def test_nested_tags_in_value_stripped(self):
        chunk = 'Link<div class="m"><div><a href="x">click</a></div>'
        record = self.parser._extract_key_value_pairs(chunk)
        self.assertEqual(record.get("Link"), "click")


class TestParseSections(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ignored_categories_skipped(self):
        body = (
            '<div class="content-pane" id="property-photos">'
            'Photo<div class="m"><div>foo.jpg</div></div></div>'
        )
        path = _write_html(self.dir, "records.html", body)
        result = GenericCategoryParser(str(path)).parse()
        ids = {c.category_id for c in result}
        self.assertNotIn("photos", ids)

    def test_generic_category_extracted(self):
        body = (
            '<div class="content-pane" id="property-request_parameters">'
            '<div class="t o">User Agent<div class="m"><div>Mozilla/5.0</div></div></div>'
            "</div>"
        )
        path = _write_html(self.dir, "records.html", body)
        result = GenericCategoryParser(str(path)).parse()

        self.assertTrue(any(c.category_id == "request_parameters" for c in result))
        cat = next(c for c in result if c.category_id == "request_parameters")
        self.assertEqual(cat.category_name, "Request Parameters")
        self.assertTrue(len(cat.records) >= 1)

    def test_no_responsive_records_skipped(self):
        body = (
            '<div class="content-pane" id="property-devices">' "No responsive records found</div>"
        )
        path = _write_html(self.dir, "records.html", body)
        result = GenericCategoryParser(str(path)).parse()
        self.assertEqual(result, [])

    def test_empty_file_returns_empty_list(self):
        path = _write_html(self.dir, "records.html", "")
        self.assertEqual(GenericCategoryParser(str(path)).parse(), [])

    def test_missing_file_returns_empty_list(self):
        missing = self.dir / "nope.html"
        self.assertEqual(GenericCategoryParser(str(missing)).parse(), [])


class TestIgnoreCategoriesConstant(unittest.TestCase):
    def test_known_dedicated_parsers_are_ignored(self):
        for cat in ("unified_messages", "photos", "videos", "archived_stories"):
            self.assertIn(cat, IGNORE_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
