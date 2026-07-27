"""
Testes para o módulo media_parser.py - Parser de fotos, vídeos e stories
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.constants import set_timezone_offset
from meta_chat_exporter.media_parser import MediaParser
from meta_chat_exporter.models import Photo, ProfileMedia, Video


def _photo_entry(media_id="1234567890123", path="linked_media/photo_1.jpg", extra=""):
    return (
        f'Linked Media File:<div class="m"><div>{path}</div>'
        f'Id<div class="m"><div>{media_id}<div class="p">'
        f'Taken<div class="m"><div>2024-01-15 10:30:00 UTC</div>'
        f'Owner<div class="m"><div>alice</div>'
        f'Privacy Setting<div class="m"><div>Public</div>'
        f'Like Count<div class="m"><div>5</div>'
        f"{extra}"
    )


def _section(name, *entries):
    inner = "".join(entries)
    return f'<div class="content-pane" id="property-{name}"><div class="t o">{inner}</div></div>'


def _write(directory: Path, body: str) -> Path:
    path = directory / "records.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return path


class TestMediaParserPhotos(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        set_timezone_offset(timedelta(hours=-3))

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_photo_parsed(self):
        body = _section("photos", _photo_entry())
        result = MediaParser(str(_write(self.dir, body))).parse()

        self.assertIsInstance(result, ProfileMedia)
        self.assertEqual(len(result.photos), 1)
        photo = result.photos[0]
        self.assertIsInstance(photo, Photo)
        self.assertEqual(photo.photo_id, "1234567890123")
        self.assertEqual(photo.local_path, "linked_media/photo_1.jpg")
        self.assertEqual(photo.owner, "alice")
        self.assertEqual(photo.privacy, "Public")
        self.assertEqual(photo.like_count, 5)
        self.assertEqual(photo.category, "Photos")

    def test_multiple_photos_split(self):
        body = _section(
            "photos",
            _photo_entry(media_id="1111111111111", path="linked_media/a.jpg"),
            _photo_entry(media_id="2222222222222", path="linked_media/b.jpg"),
        )
        result = MediaParser(str(_write(self.dir, body))).parse()
        self.assertEqual(len(result.photos), 2)
        self.assertEqual({p.photo_id for p in result.photos}, {"1111111111111", "2222222222222"})

    def test_timestamp_timezone_applied(self):
        body = _section("photos", _photo_entry())
        result = MediaParser(str(_write(self.dir, body))).parse()
        # 10:30 UTC com offset -3 => 07:30 local
        self.assertEqual(result.photos[0].taken, datetime(2024, 1, 15, 7, 30, 0))

    def test_entry_without_id_skipped(self):
        entry = (
            'Linked Media File:<div class="m"><div>linked_media/x.jpg</div>'
            'Owner<div class="m"><div>bob</div>'
        )
        body = _section("photos", entry)
        result = MediaParser(str(_write(self.dir, body))).parse()
        self.assertEqual(result.photos, [])


class TestMediaParserVideos(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        set_timezone_offset(timedelta(hours=-3))

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_video_parsed(self):
        body = _section("videos", _photo_entry(path="linked_media/video_1.mp4"))
        result = MediaParser(str(_write(self.dir, body))).parse()
        self.assertEqual(len(result.videos), 1)
        self.assertIsInstance(result.videos[0], Video)
        self.assertEqual(result.videos[0].local_path, "linked_media/video_1.mp4")
        self.assertEqual(result.videos[0].category, "Videos")


class TestMediaParserSecurity(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        set_timezone_offset(timedelta(hours=-3))

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_traversal_rejected(self):
        body = _section("photos", _photo_entry(path="../../../etc/passwd"))
        result = MediaParser(str(_write(self.dir, body))).parse()
        self.assertEqual(result.photos, [])


class TestMediaParserEdgeCases(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        set_timezone_offset(timedelta(hours=-3))

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_responsive_records(self):
        body = '<div class="content-pane" id="property-photos">' "No responsive records found</div>"
        result = MediaParser(str(_write(self.dir, body))).parse()
        self.assertTrue(result.is_empty)

    def test_empty_file(self):
        result = MediaParser(str(_write(self.dir, ""))).parse()
        self.assertTrue(result.is_empty)

    def test_missing_file(self):
        result = MediaParser(str(self.dir / "nope.html")).parse()
        self.assertTrue(result.is_empty)


if __name__ == "__main__":
    unittest.main()
