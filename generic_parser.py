"""
Meta Platforms Chat Exporter - Generic Category Parser
Parser dinâmico para extrair categorias não-específicas dos registros da Meta
"""

import html
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from models import GenericRecord, GenericCategory

logger = logging.getLogger(__name__)

# Regex pré-compilados no nível do módulo
_RE_SECTION_PRIMARY = re.compile(r'class="content-pane"[^>]*id="property-([^"]+)"', re.IGNORECASE)
_RE_SECTION_FALLBACK = re.compile(r'<div[^>]+id="property-([^"]+)"')
_RE_KV_PAIR = re.compile(
    r'([^<>]+?)(?:</div>|<br\s*/?>|<\/?a[^>]*>|\s)*<div class="m"><div>(.*?)</div>',
    re.DOTALL
)

# Categorias ignoradas pelo parser genérico por já possuírem parsers dedicados
IGNORE_CATEGORIES = {
    'unified_messages', 
    'threads_unified_messages', 
    'photos', 
    'profile_picture', 
    'videos', 
    'live_videos', 
    'archived_live_videos', 
    'archived_stories', 
    'unarchived_stories'
}

class GenericCategoryParser:
    """Parser dinâmico para identificar e extrair qualquer categoria no HTML da Meta"""

    def __init__(self, html_path: str, log_callback=None):
        self.html_path = Path(html_path)
        self.source_filename = self.html_path.name
        self.log = log_callback or (lambda x: None)

    def _read_file(self) -> Optional[str]:
        """Lê o arquivo HTML com fallback de encoding"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(self.html_path, 'r', encoding=encoding, buffering=1024*1024) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except (PermissionError, OSError) as e:
                logger.error("Erro ao ler %s: %s", self.html_path, e)
                return None
        logger.error("Nenhum encoding funcionou para: %s", self.html_path)
        return None

    def parse(self) -> List[GenericCategory]:
        """Faz a varredura das categorias dinâmicas"""
        content = self._read_file()
        if not content:
            return []

        categories = []
        
        # Encontra blocos property-XXX
        matches = list(_RE_SECTION_PRIMARY.finditer(content))
        
        # Fallback caso a classe mude (limita a <div> tags para evitar match em conteúdo):
        if not matches:
             matches = list(_RE_SECTION_FALLBACK.finditer(content))

        for i, match in enumerate(matches):
            cat_id = match.group(1)
            
            # Pula categorias geridas pelos outros parsers
            if cat_id in IGNORE_CATEGORIES:
                continue

            start = match.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(content)
            
            section_html = content[start:end]
            
            if 'No responsive records' in section_html:
                continue
                
            # Verifica se há dados
            if '<div class="t' not in section_html and '<div class="m">' not in section_html:
                 continue

            cat_name = self._format_category_name(cat_id)
            records = self._parse_section_records(section_html)
            
            if records:
                categories.append(GenericCategory(
                    category_id=cat_id,
                    category_name=cat_name,
                    records=records
                ))
                self.log(f"🔎 Categoria Genérica Extraída: {cat_name} ({len(records)} registros)")

        return categories

    def _format_category_name(self, cat_id: str) -> str:
        """Formata request_parameters para Request Parameters"""
        words = cat_id.replace('_', ' ').split()
        return " ".join(word.capitalize() for word in words)

    def _parse_section_records(self, section_html: str) -> List[GenericRecord]:
        """Converte uma seção de HTML do Meta num array de GenericRecords"""
        records = []
        
        # O HTML da Meta usa `<div class="t o">` para separar registros maiores
        chunks = re.split(r'<div class="t o">', section_html)
        
        for chunk in chunks:
            record = self._extract_key_value_pairs(chunk)
            if record:
                 records.append(GenericRecord(entries=[record]))
                
        # Caso não haja divisão class "t o", tentamos parsear como um registro gigante
        if not records:
             record = self._extract_key_value_pairs(section_html)
             if record:
                  records.append(GenericRecord(entries=[record]))

        return records
        
    def _extract_key_value_pairs(self, html_chunk: str) -> Dict[str, str]:
        """Extrai pares chave-valor com heurística de regex"""
        # Meta template genérico:  `Texto da Chave<div class="m"><div>Texto do Valor</div>`
        dict_record = {}
        
        # Regex flexível para pegar chave (texto anterior) e valor (dentro do div class m)
        matches = _RE_KV_PAIR.finditer(html_chunk)
        for match in matches:
            key = html.unescape(match.group(1)).strip()
            # Remover whitespaces extras interconectados
            key = re.sub(r'\s+', ' ', key)
            
            val = match.group(2).strip()
            # Se ainda tiver divs aninhados no val, removemos ou extraímos (ex: mídias conectadas)
            val = re.sub(r'<[^>]+>', ' ', val)
            val = html.unescape(val).strip()
            val = re.sub(r'\s+', ' ', val)
            
            # Sanitização de chave: Evita capturar muito lixo que não é chave (geralmente chaves são curtas, sob 80 chars)
            if len(key) > 80 or not key: 
                continue
            
            if key in dict_record:
                # Junta valores múltiplos da mesma chave num array simulado
                dict_record[key] += f" | {val}"
            else:
                dict_record[key] = val
                
        return dict_record
