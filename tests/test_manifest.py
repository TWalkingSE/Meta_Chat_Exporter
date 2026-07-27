"""Testes do manifesto de cadeia de custódia (F4)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.manifest import (
    build_custody_manifest,
    discover_source_htmls,
    is_source_html,
    sha256_file,
    write_custody_manifest,
    write_manifest_for_export,
)


class TestIsSourceHtml(unittest.TestCase):
    def test_meta_html_is_source(self):
        self.assertTrue(is_source_html(Path("your_facebook_activity.html")))

    def test_generated_exports_excluded(self):
        self.assertFalse(is_source_html(Path("chat_alice_12345678.html")))
        self.assertFalse(is_source_html(Path("todas_conversas_20240101_120000.html")))
        self.assertFalse(is_source_html(Path("filtradas_redigido_x.html")))
        self.assertFalse(is_source_html(Path("conversas_20240101.json")))


class TestSha256AndManifest(unittest.TestCase):
    def test_sha256_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.html"
            p.write_bytes(b"hello-world")
            h1 = sha256_file(p)
            h2 = sha256_file(p)
            self.assertEqual(h1, h2)
            self.assertEqual(len(h1), 64)

    def test_discover_and_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "messages.html"
            src.write_text("<html>meta</html>", encoding="utf-8")
            (base / "todas_conversas_x.html").write_text("<html>out</html>", encoding="utf-8")

            found = discover_source_htmls(base)
            self.assertEqual([f.name for f in found], ["messages.html"])

            out = base / "export.html"
            out.write_text("<html>export</html>", encoding="utf-8")

            manifest = build_custody_manifest(
                found,
                base_dir=base,
                output_files=[out],
                app_version="5.4",
            )
            self.assertEqual(manifest["schema"], "meta-chat-exporter.custody_manifest.v1")
            self.assertEqual(manifest["meta"]["source_count"], 1)
            self.assertEqual(len(manifest["sources"]), 1)
            self.assertEqual(manifest["sources"][0]["path"], "messages.html")
            self.assertEqual(len(manifest["outputs"]), 1)
            self.assertTrue(manifest["meta"]["sources_aggregate_sha256"])

            path = write_custody_manifest(manifest, base / "manifesto_test.json")
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["meta"]["app_version"], "5.4")

    def test_write_manifest_for_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / "inbox.html"
            src.write_text("x", encoding="utf-8")
            out = base / "todas_conversas_1.html"
            out.write_text("y", encoding="utf-8")

            path = write_manifest_for_export(
                base,
                [src],
                output_files=[out],
                stem="manifesto_html",
                app_version="5.4",
            )
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
            self.assertTrue(path.name.startswith("manifesto_html_"))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["meta"]["source_count"], 1)


if __name__ == "__main__":
    unittest.main()
