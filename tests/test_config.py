"""
Testes para o módulo config.py - Configuração persistente
"""

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.config import DEFAULT_CONFIG, Config


class TestConfigDefaults(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_defaults_when_file_missing(self):
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.get_all(), DEFAULT_CONFIG)
        self.assertFalse(self.path.exists())

    def test_properties_match_defaults(self):
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.timezone_offset_hours, DEFAULT_CONFIG["timezone_offset_hours"])
        self.assertEqual(cfg.cache_enabled, DEFAULT_CONFIG["cache_enabled"])
        self.assertEqual(cfg.whisper_model, DEFAULT_CONFIG["whisper_model"])
        self.assertEqual(cfg.whisper_language, DEFAULT_CONFIG["whisper_language"])
        self.assertEqual(cfg.pagination_size, DEFAULT_CONFIG["pagination_size"])
        self.assertEqual(cfg.dark_mode, DEFAULT_CONFIG["dark_mode"])
        self.assertEqual(cfg.log_level, DEFAULT_CONFIG["log_level"])


class TestConfigPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_set_persists_to_disk(self):
        cfg = Config(config_path=self.path)
        cfg.set("whisper_model", "large-v3")
        self.assertTrue(self.path.exists())

        reloaded = Config(config_path=self.path)
        self.assertEqual(reloaded.get("whisper_model"), "large-v3")

    def test_property_setter_saves(self):
        cfg = Config(config_path=self.path)
        cfg.timezone_offset_hours = -5
        reloaded = Config(config_path=self.path)
        self.assertEqual(reloaded.timezone_offset_hours, -5)

    def test_get_returns_default_for_unknown_key(self):
        cfg = Config(config_path=self.path)
        self.assertIsNone(cfg.get("does_not_exist"))
        self.assertEqual(cfg.get("does_not_exist", "fallback"), "fallback")

    def test_extra_user_keys_are_preserved(self):
        self.path.write_text(json.dumps({"custom_key": "custom_value"}), encoding="utf-8")
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.get("custom_key"), "custom_value")


class TestConfigValidation(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_wrong_type_falls_back_to_default(self):
        # pagination_size deve ser int; fornecer string deve ser rejeitado
        self.path.write_text(json.dumps({"pagination_size": "not-an-int"}), encoding="utf-8")
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.pagination_size, DEFAULT_CONFIG["pagination_size"])

    def test_valid_type_is_accepted(self):
        self.path.write_text(json.dumps({"pagination_size": 1000}), encoding="utf-8")
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.pagination_size, 1000)

    def test_corrupted_json_falls_back_to_defaults(self):
        self.path.write_text("{ this is not valid json ", encoding="utf-8")
        cfg = Config(config_path=self.path)
        self.assertEqual(cfg.get_all(), DEFAULT_CONFIG)

    def test_get_all_returns_copy(self):
        cfg = Config(config_path=self.path)
        snapshot = cfg.get_all()
        snapshot["dark_mode"] = "mutated"
        self.assertEqual(cfg.dark_mode, DEFAULT_CONFIG["dark_mode"])


if __name__ == "__main__":
    unittest.main()
