"""
Meta Platforms Chat Exporter - Injeção de Transcrições em HTML Exportado
Permite adicionar transcrições a um arquivo HTML já exportado anteriormente.
"""

import html
import shutil
import re
import logging
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Regex pré-compilado no nível do módulo (evita recompilação a cada chamada)
_RE_AUDIO_BLOCK = re.compile(
    r'(<div\s+class="audio-container">.*?</div>\s*</div>)'  # audio-container completo
    r'(\s*<div\s+class="audio-transcription">.*?</div>)?'   # transcrição existente (opcional)
    r'(\s*<div\s+class="attachment-filename">)(.*?)(</div>)',  # filename
    re.DOTALL
)


def _build_transcription_html(text: str) -> str:
    """Gera o bloco HTML de transcrição (compatível com o formato dos geradores)."""
    escaped = html.escape(text)
    return (
        '<div class="audio-transcription">'
        '<span class="transcription-label">Transcrição:</span>'
        f'<span class="transcription-text"><em>{escaped}</em></span>'
        '</div>'
    )


def inject_transcriptions_into_html(
    html_path: Path,
    transcriptions: Dict[str, str],
) -> Tuple[int, int]:
    """
    Injeta transcrições em um arquivo HTML exportado.

    Procura blocos de áudio no HTML e, para cada um que ainda não
    possui transcrição, insere o bloco correspondente se houver
    transcrição disponível no dicionário.

    Args:
        html_path: Caminho para o arquivo HTML exportado.
        transcriptions: Dict {filename_lower: transcription_text}.

    Returns:
        Tuple (injetadas, já_existentes).
    """
    if not html_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {html_path}")

    if not transcriptions:
        return 0, 0

    content = html_path.read_text(encoding="utf-8")

    injected = 0
    already_present = 0

    # Usa regex pré-compilado no nível do módulo
    pattern = _RE_AUDIO_BLOCK

    def _replacer(match):
        nonlocal injected, already_present

        audio_block = match.group(1)
        existing_transcription = match.group(2)
        filename_open = match.group(3)
        filename_text = match.group(4)
        filename_close = match.group(5)

        # Se já tem transcrição, não duplicar
        if existing_transcription and existing_transcription.strip():
            already_present += 1
            return match.group(0)

        # Extrair nome do arquivo e buscar transcrição
        clean_name = re.sub(r'<[^>]+>', '', filename_text).strip()
        if not clean_name:
            return match.group(0)

        # Tentar encontrar transcrição (mesmo algoritmo do BaseHTMLGenerator)
        text = _find_transcription(clean_name, transcriptions)
        if not text:
            return match.group(0)

        # Injetar transcrição entre o audio-container e o attachment-filename
        transcription_html = _build_transcription_html(text)
        injected += 1

        return (
            audio_block
            + "\n                " + transcription_html
            + filename_open + filename_text + filename_close
        )

    new_content = pattern.sub(_replacer, content)

    if injected > 0:
        # Criar backup antes de sobrescrever o original
        backup_path = html_path.with_suffix(html_path.suffix + ".bak")
        try:
            shutil.copy2(html_path, backup_path)
            logger.debug("Backup criado: %s", backup_path)
        except OSError as e:
            logger.warning("Não foi possível criar backup: %s", e)
        html_path.write_text(new_content, encoding="utf-8")
        logger.info("Injetadas %d transcrições em %s", injected, html_path.name)

    return injected, already_present


def _find_transcription(filename: str, transcriptions: Dict[str, str]) -> str:
    """Busca transcrição para um arquivo de áudio (lógica compatível com BaseHTMLGenerator)."""
    if not filename:
        return ""

    filename_lower = filename.lower()
    if filename_lower in transcriptions:
        return transcriptions[filename_lower]

    # Sem extensão
    name_no_ext = filename_lower.rsplit('.', 1)[0] if '.' in filename_lower else filename_lower
    if name_no_ext in transcriptions:
        return transcriptions[name_no_ext]

    # Apenas basename
    basename = filename_lower.split('/')[-1].split('\\')[-1]
    if basename in transcriptions:
        return transcriptions[basename]

    basename_no_ext = basename.rsplit('.', 1)[0] if '.' in basename else basename
    if basename_no_ext in transcriptions:
        return transcriptions[basename_no_ext]

    return ""
