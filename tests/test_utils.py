"""
Testes para o módulo utils.py - Funções utilitárias
"""

import os
import sys
import unittest

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.utils import (
    clean_message_body,
    escape_html,
    get_file_type,
    is_safe_relative_path,
    is_safe_url,
    translate_message,
)


class TestEscapeHtml(unittest.TestCase):
    """Testes para o escape centralizado de HTML"""

    def test_escapa_menor_que(self):
        self.assertEqual(escape_html("a < b"), "a &lt; b")

    def test_escapa_maior_que(self):
        self.assertEqual(escape_html("a > b"), "a &gt; b")

    def test_escapa_e_comercial(self):
        self.assertEqual(escape_html("Tom & Jerry"), "Tom &amp; Jerry")

    def test_escapa_aspas_duplas(self):
        self.assertEqual(escape_html('diz "olá"'), "diz &quot;olá&quot;")

    def test_escapa_aspas_simples(self):
        self.assertEqual(escape_html("don't"), "don&#x27;t")

    def test_escapa_tag_completa(self):
        # Combina <, >, & e aspas em um cenário realista de XSS
        self.assertEqual(
            escape_html('<script>alert("x")</script>'),
            "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;",
        )

    def test_none_vira_string_vazia(self):
        self.assertEqual(escape_html(None), "")

    def test_inteiro_convertido_para_str(self):
        self.assertEqual(escape_html(42), "42")

    def test_lista_convertida_para_str(self):
        # Valor não-str é convertido com str() e então escapado
        self.assertEqual(escape_html([1, 2]), "[1, 2]")

    def test_valor_nao_str_com_caracteres_especiais(self):
        # str() de um valor não-str que produz caracteres especiais é escapado
        self.assertEqual(escape_html(["<a>"]), "[&#x27;&lt;a&gt;&#x27;]")

    def test_string_sem_caracteres_especiais(self):
        self.assertEqual(escape_html("texto simples"), "texto simples")

    def test_string_vazia(self):
        self.assertEqual(escape_html(""), "")


class TestCleanMessageBody(unittest.TestCase):
    """Testes para limpeza de corpo de mensagem"""

    def test_remove_html_tags(self):
        text = "Hello <b>world</b> <i>today</i>"
        result = clean_message_body(text)
        self.assertEqual(result, "Hello world today")

    def test_remove_page_break(self):
        text = "Hello Meta Platforms Business Record Page 42 World"
        result = clean_message_body(text)
        self.assertNotIn("Meta Platforms Business Record Page", result)
        self.assertIn("Hello", result)
        self.assertIn("World", result)

    def test_normalize_spaces(self):
        text = "Hello    World   Test"
        result = clean_message_body(text)
        self.assertEqual(result, "Hello World Test")

    def test_empty_string(self):
        self.assertEqual(clean_message_body(""), "")

    def test_none_input(self):
        self.assertIsNone(clean_message_body(None))

    def test_strip_whitespace(self):
        text = "  Hello World  "
        result = clean_message_body(text)
        self.assertEqual(result, "Hello World")

    def test_complex_html(self):
        text = '<div class="test">Content</div><span>More</span>'
        result = clean_message_body(text)
        self.assertEqual(result, "ContentMore")


class TestTranslateMessage(unittest.TestCase):
    """Testes para tradução de mensagens"""

    def test_exact_match(self):
        result = translate_message("sent a voice message.")
        self.assertEqual(result, "enviou uma mensagem de voz.")

    def test_exact_match_with_you(self):
        result = translate_message("You sent a voice message.")
        self.assertEqual(result, "Você enviou uma mensagem de voz.")

    def test_partial_match(self):
        result = translate_message("John started a video chat.")
        self.assertIn("chamada de vídeo", result)

    def test_no_match(self):
        result = translate_message("Custom message without keywords")
        self.assertEqual(result, "Custom message without keywords")

    def test_empty_string(self):
        result = translate_message("")
        self.assertEqual(result, "")

    def test_none_input(self):
        result = translate_message(None)
        self.assertIsNone(result)

    def test_multiple_translations_applied(self):
        """Verifica que múltiplas traduções são aplicadas (sem break)"""
        # Mensagem com múltiplas palavras traduzíveis
        result = translate_message("Liked a message Replied to you")
        self.assertIn("Curtiu uma mensagem", result)
        self.assertIn("Respondeu a", result)

    def test_call_translations(self):
        result = translate_message("You started an audio call")
        self.assertEqual(result, "Você iniciou uma chamada de áudio")

    def test_missed_call(self):
        result = translate_message("Missed call")
        self.assertEqual(result, "Chamada perdida")

    def test_screenshot(self):
        result = translate_message("You took a screenshot.")
        self.assertEqual(result, "Você tirou uma captura de tela.")

    def test_group_actions(self):
        result = translate_message("John created the group")
        self.assertIn("criou o grupo", result)


class TestGetFileType(unittest.TestCase):
    """Testes para detecção de tipo de arquivo"""

    def test_mp3(self):
        self.assertEqual(get_file_type("music.mp3"), "audio/mpeg")

    def test_m4a(self):
        self.assertEqual(get_file_type("voice.m4a"), "audio/mp4")

    def test_aac(self):
        self.assertEqual(get_file_type("sound.aac"), "audio/aac")

    def test_wav(self):
        self.assertEqual(get_file_type("recording.wav"), "audio/wav")

    def test_ogg(self):
        self.assertEqual(get_file_type("audio.ogg"), "audio/ogg")

    def test_mp4_video(self):
        self.assertEqual(get_file_type("video_clip.mp4"), "video/mp4")

    def test_mp4_audio(self):
        self.assertEqual(get_file_type("audioclip_001.mp4"), "audio/mpeg")

    def test_mp4_voice(self):
        self.assertEqual(get_file_type("voice_message.mp4"), "audio/mpeg")

    def test_mp4_mensagem_de_voz(self):
        self.assertEqual(get_file_type("mensagem_de_voz_001.mp4"), "audio/mpeg")

    def test_jpg(self):
        self.assertEqual(get_file_type("photo.jpg"), "image/jpeg")

    def test_jpeg(self):
        self.assertEqual(get_file_type("photo.jpeg"), "image/jpeg")

    def test_png(self):
        self.assertEqual(get_file_type("screenshot.png"), "image/png")

    def test_gif(self):
        self.assertEqual(get_file_type("animation.gif"), "image/gif")

    def test_webp(self):
        self.assertEqual(get_file_type("image.webp"), "image/webp")

    def test_unknown(self):
        self.assertEqual(get_file_type("document.pdf"), "unknown")

    def test_path_with_dirs(self):
        self.assertEqual(get_file_type("photos/sub/image.png"), "image/png")

    def test_uppercase_extension(self):
        self.assertEqual(get_file_type("PHOTO.JPG"), "image/jpeg")


class TestIsSafeRelativePath(unittest.TestCase):
    """Testes para a validação de caminhos relativos seguros"""

    def test_simple_relative(self):
        self.assertTrue(is_safe_relative_path("photos/image.jpg"))

    def test_filename_only(self):
        self.assertTrue(is_safe_relative_path("foto.png"))

    def test_dot_in_filename_is_safe(self):
        # Não deve ter falso-positivo com ".." dentro do nome do arquivo
        self.assertTrue(is_safe_relative_path("foto..jpg"))
        self.assertTrue(is_safe_relative_path("a/b..c/d.png"))

    def test_leading_dot_slash(self):
        self.assertTrue(is_safe_relative_path("./photos/x.jpg"))

    def test_empty_is_unsafe(self):
        self.assertFalse(is_safe_relative_path(""))

    def test_parent_traversal_unsafe(self):
        self.assertFalse(is_safe_relative_path("../etc/passwd"))
        self.assertFalse(is_safe_relative_path("a/../../b"))
        self.assertFalse(is_safe_relative_path(".."))

    def test_absolute_posix_unsafe(self):
        self.assertFalse(is_safe_relative_path("/etc/passwd"))

    def test_windows_drive_unsafe(self):
        self.assertFalse(is_safe_relative_path("C:/Windows/system32"))
        self.assertFalse(is_safe_relative_path("C:\\Windows\\system32"))

    def test_backslash_traversal_unsafe(self):
        self.assertFalse(is_safe_relative_path("..\\secret"))
        self.assertFalse(is_safe_relative_path("a\\..\\b"))

    def test_unc_path_unsafe(self):
        self.assertFalse(is_safe_relative_path("\\\\server\\share"))


class TestIsSafeUrl(unittest.TestCase):
    def test_http_https_mailto_ok(self):
        self.assertTrue(is_safe_url("https://example.com/x"))
        self.assertTrue(is_safe_url("http://example.com"))
        self.assertTrue(is_safe_url("mailto:a@b.com"))

    def test_javascript_and_data_rejected(self):
        self.assertFalse(is_safe_url("javascript:alert(1)"))
        self.assertFalse(is_safe_url("data:text/html,hi"))
        self.assertFalse(is_safe_url("vbscript:msgbox(1)"))

    def test_empty_and_relative_rejected(self):
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url(None))
        self.assertFalse(is_safe_url("/path/only"))
        self.assertFalse(is_safe_url("//evil.example/x"))


if __name__ == "__main__":
    unittest.main()
