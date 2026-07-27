"""
Testes de exemplo para o pacote de internacionalização (i18n).

Cobre a seleção de recurso de idioma (R36.3), verificando as strings de
interface retornadas por idioma, e a origem externa das listas de stop words
e de idiomas (R36.1, R36.2). Garante ainda o fallback para o idioma padrão
(pt) quando um idioma inválido é selecionado.
"""

import os
import sys
import unittest

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter import i18n
from meta_chat_exporter.i18n import detection, en, pt


class TestSelecaoDeIdioma(unittest.TestCase):
    """Seleção de recurso de idioma e strings retornadas (R36.1, R36.3)."""

    def tearDown(self):
        # Restaura o idioma global para o padrão e evita vazar estado entre testes.
        i18n.set_language("pt")

    def test_selecionar_en_retorna_strings_em_ingles(self):
        # Selecionar "en" deve apresentar as strings de UI em inglês (R36.3).
        i18n.set_language("en")
        self.assertEqual(i18n.get_language(), "en")
        # A string para uma chave conhecida deve vir do recurso en...
        self.assertEqual(i18n.get_string("stats_summary"), en.UI_STRINGS["stats_summary"])
        self.assertEqual(i18n.get_string("stats_summary"), "Overview")
        # ...e diferir do valor em português.
        self.assertNotEqual(i18n.get_string("stats_summary"), pt.UI_STRINGS["stats_summary"])

    def test_selecionar_pt_retorna_strings_em_portugues(self):
        # Selecionar "pt" deve apresentar as strings de UI em português (R36.3).
        i18n.set_language("pt")
        self.assertEqual(i18n.get_language(), "pt")
        self.assertEqual(i18n.get_string("stats_summary"), pt.UI_STRINGS["stats_summary"])
        self.assertEqual(i18n.get_string("stats_summary"), "Resumo geral")

    def test_parametro_lang_nao_altera_idioma_global(self):
        # O parâmetro lang opcional obtém recursos sem mudar o idioma selecionado.
        i18n.set_language("pt")
        self.assertEqual(i18n.get_string("stats_media", lang="en"), "Media")
        # O idioma global permanece pt.
        self.assertEqual(i18n.get_language(), "pt")
        self.assertEqual(i18n.get_string("stats_media"), "Mídias")

    def test_get_strings_corresponde_ao_recurso(self):
        # get_strings deve retornar o dicionário de UI do recurso selecionado.
        self.assertEqual(i18n.get_strings(lang="en"), en.UI_STRINGS)
        self.assertEqual(i18n.get_strings(lang="pt"), pt.UI_STRINGS)

    def test_idiomas_disponiveis(self):
        # Ambos os recursos implementados devem estar disponíveis.
        self.assertIn("pt", i18n.available_languages())
        self.assertIn("en", i18n.available_languages())


class TestOrigemExternaDasListas(unittest.TestCase):
    """As listas de stop words e idiomas vêm de recursos externos (R36.2)."""

    def tearDown(self):
        i18n.set_language("pt")

    def test_stop_words_vem_do_modulo_de_recurso(self):
        # get_stop_words deve refletir exatamente o conjunto do módulo de recurso.
        self.assertIsInstance(i18n.get_stop_words(lang="pt"), set)
        self.assertEqual(i18n.get_stop_words(lang="pt"), pt.STOP_WORDS)
        self.assertEqual(i18n.get_stop_words(lang="en"), en.STOP_WORDS)

    def test_stop_words_diferem_entre_idiomas(self):
        # Os conjuntos de stop words de pt e en devem ser distintos.
        self.assertNotEqual(i18n.get_stop_words(lang="pt"), i18n.get_stop_words(lang="en"))

    def test_stop_words_retorna_copia(self):
        # A mutação do resultado não deve afetar o módulo de recurso.
        palavras = i18n.get_stop_words(lang="pt")
        palavras.add("__token_temporario__")
        self.assertNotIn("__token_temporario__", pt.STOP_WORDS)

    def test_lang_keywords_vem_do_modulo_de_deteccao(self):
        # get_lang_keywords deve refletir o mapa de palavras-chave de detection.
        keywords = i18n.get_lang_keywords()
        self.assertIsInstance(keywords, dict)
        self.assertEqual(set(keywords.keys()), set(detection.LANG_KEYWORDS.keys()))
        for idioma, palavras in detection.LANG_KEYWORDS.items():
            self.assertEqual(keywords[idioma], set(palavras))

    def test_lang_code_map_vem_do_modulo_de_deteccao(self):
        # get_lang_code_map deve refletir o mapa de códigos ISO de detection.
        self.assertEqual(i18n.get_lang_code_map(), detection.LANG_CODE_MAP)
        self.assertEqual(i18n.get_lang_code_map()["en"], "English")

    def test_weekday_names_vem_do_modulo_de_recurso(self):
        # Os nomes dos dias da semana são externalizados por idioma.
        self.assertEqual(i18n.get_weekday_names(lang="pt"), pt.WEEKDAY_NAMES)
        self.assertEqual(i18n.get_weekday_names(lang="en"), en.WEEKDAY_NAMES)


class TestFallbackIdiomaInvalido(unittest.TestCase):
    """Idioma inválido recai para o padrão (pt)."""

    def tearDown(self):
        i18n.set_language("pt")

    def test_set_language_invalido_cai_no_padrao(self):
        i18n.set_language("xx")
        self.assertEqual(i18n.get_language(), i18n.DEFAULT_LANGUAGE)
        self.assertEqual(i18n.get_language(), "pt")

    def test_get_string_com_lang_invalido_usa_padrao(self):
        # Com idioma inválido, as strings retornam no idioma padrão (pt).
        self.assertEqual(i18n.get_string("stats_summary", lang="xx"), "Resumo geral")

    def test_get_stop_words_com_lang_invalido_usa_padrao(self):
        self.assertEqual(i18n.get_stop_words(lang="xx"), pt.STOP_WORDS)


if __name__ == "__main__":
    unittest.main()
