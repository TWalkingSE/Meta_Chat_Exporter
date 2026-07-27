"""
Manifesto de cadeia de custódia (F4).

Gera um registro JSON com SHA-256 dos arquivos HTML de entrada (e, opcionalmente,
dos artefatos de saída), para preservar evidência de integridade em exportações
investigativas.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Prefixo de arquivos gerados por este programa (não entram como "fonte Meta")
_GENERATED_PREFIXES = ("chat_", "todas_conversas_", "filtradas_", "conversas_")


def is_source_html(path: Path) -> bool:
    """True se o arquivo parece ser HTML de entrada da Meta (não gerado por nós)."""
    name = path.name
    if not name.lower().endswith(".html"):
        return False
    return not any(name.startswith(p) for p in _GENERATED_PREFIXES)


def discover_source_htmls(folder: Path) -> list[Path]:
    """Lista HTMLs de entrada em ``folder`` (não gerados pelo exporter)."""
    folder = Path(folder)
    files = [p for p in folder.glob("*.html") if p.is_file() and is_source_html(p)]
    return sorted(files, key=lambda p: p.name.lower())


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calcula SHA-256 de um arquivo em chunks (adequado a arquivos grandes)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_file_entry(path: Path, *, base_dir: Path | None = None) -> dict[str, Any]:
    """Monta o registro de um arquivo: nome, tamanho, mtime, sha256."""
    path = Path(path)
    stat = path.stat()
    rel = path.name
    if base_dir is not None:
        try:
            rel = str(path.resolve().relative_to(Path(base_dir).resolve()))
        except ValueError:
            rel = path.name
    return {
        "path": rel,
        "size_bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
        "sha256": sha256_file(path),
    }


def build_custody_manifest(
    source_files: Iterable[Path],
    *,
    base_dir: Path | None = None,
    output_files: Iterable[Path] | None = None,
    app_version: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Constrói o dicionário do manifesto de custódia.

    Args:
        source_files: HTMLs (ou outros) de entrada a hashear.
        base_dir: base para paths relativos no manifesto.
        output_files: artefatos gerados a incluir (opcional; hasheados se existirem).
        app_version: versão do exporter.
        extra: campos adicionais mesclados em ``meta``.
    """
    sources = [Path(p) for p in source_files]
    entries = []
    for p in sources:
        if not p.is_file():
            logger.warning("Arquivo de fonte ausente no manifesto: %s", p)
            continue
        try:
            entries.append(build_file_entry(p, base_dir=base_dir))
        except OSError as e:
            logger.warning("Falha ao hashear %s: %s", p, e)

    outputs: list[dict[str, Any]] = []
    if output_files:
        for p in output_files:
            p = Path(p)
            if not p.is_file():
                continue
            try:
                outputs.append(build_file_entry(p, base_dir=base_dir))
            except OSError as e:
                logger.warning("Falha ao hashear saída %s: %s", p, e)

    # Hash agregado estável das fontes (ordenado por path)
    concat = "".join(e["sha256"] for e in sorted(entries, key=lambda x: x["path"]))
    aggregate = hashlib.sha256(concat.encode("ascii")).hexdigest() if entries else ""

    meta: dict[str, Any] = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "app_version": app_version,
        "algorithm": "SHA-256",
        "source_count": len(entries),
        "sources_aggregate_sha256": aggregate,
    }
    if extra:
        meta.update(extra)

    return {
        "schema": "meta-chat-exporter.custody_manifest.v1",
        "meta": meta,
        "sources": entries,
        "outputs": outputs,
    }


def write_custody_manifest(
    manifest: dict[str, Any],
    output_path: Path,
) -> Path:
    """Grava o manifesto em JSON UTF-8 (indentado)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    logger.info("Manifesto de custódia salvo: %s", output_path)
    return output_path


def write_manifest_for_export(
    base_dir: Path,
    source_files: Iterable[Path] | None = None,
    *,
    output_files: Iterable[Path] | None = None,
    stem: str | None = None,
    app_version: str = "",
    extra: dict[str, Any] | None = None,
) -> Path | None:
    """Descobre fontes (se necessário), monta e grava o manifesto ao lado da exportação.

    Returns:
        Caminho do manifesto ou ``None`` se não houver fontes.
    """
    base_dir = Path(base_dir)
    sources = list(source_files) if source_files is not None else discover_source_htmls(base_dir)
    if not sources:
        logger.info("Nenhum HTML de fonte para manifesto em %s", base_dir)
        return None

    version = app_version
    if not version:
        try:
            from meta_chat_exporter import __version__ as pkg_version

            version = pkg_version
        except Exception:
            version = ""

    manifest = build_custody_manifest(
        sources,
        base_dir=base_dir,
        output_files=output_files,
        app_version=version,
        extra=extra,
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{stem or 'manifesto_custodia'}_{stamp}.json"
    path = base_dir / name
    return write_custody_manifest(manifest, path)
