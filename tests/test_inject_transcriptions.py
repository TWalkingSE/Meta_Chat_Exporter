"""
Testes para o módulo inject_transcriptions.py - Injeção de transcrições em HTML
"""

import sys
import os
import unittest
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inject_transcriptions import (
    inject_transcriptions_into_html,
    _build_transcription_html,
    _find_transcription,
)


# HTML de teste que simula a saída dos geradores
SAMPLE_HTML_NO_TRANSCRIPTION = """\
<!DOCTYPE html>
<html>
<head><title>Test Chat</title></head>
<body>
<div class="message received">
    <div class="message-bubble">
        <div class="attachment">
            <div class="audio-container">
                <audio id="audio-123" controls preload="none">
                    <source src="linked_media/audio_001.m4a" type="audio/mp4">
                </audio>
                <div class="audio-speed">
                    <button class="active" onclick="setSpeed(123, 1, this)">1x</button>
                    <button onclick="setSpeed(123, 1.5, this)">1.5x</button>
                    <button onclick="setSpeed(123, 2, this)">2x</button>
                </div>
            </div>
            <div class="attachment-filename">audio_001.m4a</div>
        </div>
    </div>
</div>
</body>
</html>
"""

SAMPLE_HTML_WITH_TRANSCRIPTION = """\
<!DOCTYPE html>
<html>
<head><title>Test Chat</title></head>
<body>
<div class="message received">
    <div class="message-bubble">
        <div class="attachment">
            <div class="audio-container">
                <audio id="audio-456" controls preload="none">
                    <source src="linked_media/audio_002.m4a" type="audio/mp4">
                </audio>
                <div class="audio-speed">
                    <button class="active" onclick="setSpeed(456, 1, this)">1x</button>
                </div>
            </div>
            <div class="audio-transcription"><span class="transcription-label">Transcrição:</span><span class="transcription-text"><em>Já existente</em></span></div>
            <div class="attachment-filename">audio_002.m4a</div>
        </div>
    </div>
</div>
</body>
</html>
"""

SAMPLE_HTML_NO_AUDIO = """\
<!DOCTYPE html>
<html>
<head><title>Test Chat</title></head>
<body>
<div class="message received">
    <div class="message-bubble">
        <div class="message-content">Olá mundo</div>
    </div>
</div>
</body>
</html>
"""


class TestBuildTranscriptionHtml(unittest.TestCase):
    """Testes para _build_transcription_html"""

    def test_basic_transcription(self):
        result = _build_transcription_html("Olá, como vai?")
        self.assertIn("audio-transcription", result)
        self.assertIn("transcription-label", result)
        self.assertIn("Transcrição:", result)
        self.assertIn("Olá, como vai?", result)

    def test_html_escape(self):
        result = _build_transcription_html('<script>alert("xss")</script>')
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)


class TestFindTranscription(unittest.TestCase):
    """Testes para _find_transcription"""

    def setUp(self):
        self.transcriptions = {
            "audio_001.m4a": "Transcrição do áudio 1",
            "audio_001": "Transcrição do áudio 1",
            "gravacao.ogg": "Outra mensagem",
            "gravacao": "Outra mensagem",
        }

    def test_exact_match(self):
        result = _find_transcription("audio_001.m4a", self.transcriptions)
        self.assertEqual(result, "Transcrição do áudio 1")

    def test_case_insensitive(self):
        result = _find_transcription("AUDIO_001.M4A", self.transcriptions)
        self.assertEqual(result, "Transcrição do áudio 1")

    def test_no_extension(self):
        result = _find_transcription("audio_001", self.transcriptions)
        self.assertEqual(result, "Transcrição do áudio 1")

    def test_not_found(self):
        result = _find_transcription("inexistente.mp3", self.transcriptions)
        self.assertEqual(result, "")

    def test_empty_filename(self):
        result = _find_transcription("", self.transcriptions)
        self.assertEqual(result, "")


class TestInjectTranscriptions(unittest.TestCase):
    """Testes para inject_transcriptions_into_html"""

    def setUp(self):
        self.test_dir = Path(__file__).parent
        self.test_html = self.test_dir / "test_inject_output.html"

    def tearDown(self):
        if self.test_html.exists():
            self.test_html.unlink()

    def test_inject_new_transcription(self):
        """Deve injetar transcrição onde não existe"""
        self.test_html.write_text(SAMPLE_HTML_NO_TRANSCRIPTION, encoding="utf-8")

        transcriptions = {
            "audio_001.m4a": "Olá, tudo bem?",
            "audio_001": "Olá, tudo bem?",
        }

        injected, already = inject_transcriptions_into_html(
            self.test_html, transcriptions
        )

        self.assertEqual(injected, 1)
        self.assertEqual(already, 0)

        content = self.test_html.read_text(encoding="utf-8")
        self.assertIn("audio-transcription", content)
        self.assertIn("Olá, tudo bem?", content)

    def test_no_duplicate_injection(self):
        """Não deve duplicar transcrição que já existe"""
        self.test_html.write_text(SAMPLE_HTML_WITH_TRANSCRIPTION, encoding="utf-8")

        transcriptions = {
            "audio_002.m4a": "Nova transcrição",
            "audio_002": "Nova transcrição",
        }

        injected, already = inject_transcriptions_into_html(
            self.test_html, transcriptions
        )

        self.assertEqual(injected, 0)
        self.assertEqual(already, 1)

        # Verificar que o conteúdo original foi mantido
        content = self.test_html.read_text(encoding="utf-8")
        self.assertIn("Já existente", content)
        self.assertNotIn("Nova transcrição", content)

    def test_no_audio_html(self):
        """HTML sem áudio não deve ser alterado"""
        self.test_html.write_text(SAMPLE_HTML_NO_AUDIO, encoding="utf-8")

        transcriptions = {
            "audio_001.m4a": "Uma transcrição",
        }

        injected, already = inject_transcriptions_into_html(
            self.test_html, transcriptions
        )

        self.assertEqual(injected, 0)
        self.assertEqual(already, 0)

    def test_no_matching_transcription(self):
        """Áudio sem transcrição correspondente não deve ser alterado"""
        self.test_html.write_text(SAMPLE_HTML_NO_TRANSCRIPTION, encoding="utf-8")

        transcriptions = {
            "outro_audio.m4a": "Transcrição de outro áudio",
        }

        injected, already = inject_transcriptions_into_html(
            self.test_html, transcriptions
        )

        self.assertEqual(injected, 0)
        self.assertEqual(already, 0)

    def test_empty_transcriptions_dict(self):
        """Dict vazio não deve alterar nada"""
        self.test_html.write_text(SAMPLE_HTML_NO_TRANSCRIPTION, encoding="utf-8")

        injected, already = inject_transcriptions_into_html(
            self.test_html, {}
        )

        self.assertEqual(injected, 0)
        self.assertEqual(already, 0)

    def test_file_not_found(self):
        """Deve levantar FileNotFoundError para arquivo inexistente"""
        fake_path = self.test_dir / "nao_existe.html"
        with self.assertRaises(FileNotFoundError):
            inject_transcriptions_into_html(fake_path, {"a": "b"})


if __name__ == "__main__":
    unittest.main()
