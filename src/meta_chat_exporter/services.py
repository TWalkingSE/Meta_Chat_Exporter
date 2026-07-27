"""
Serviços de cache e exportação desacoplados da camada de interface (GUI).

Estes serviços NÃO dependem de PyQt e podem ser importados e testados sem
instanciar a aplicação gráfica. A GUI (`ChatExporterApp` em `app.py`) delega
as operações de cache e exportação a estes serviços, preservando o
comportamento observável (Requisito 27).
"""

import copy
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path

from meta_chat_exporter.exporters import CSVExporter, JSONExporter
from meta_chat_exporter.generators_all import AllChatsHTMLGenerator
from meta_chat_exporter.generators_single import ChatHTMLGenerator
from meta_chat_exporter.manifest import write_manifest_for_export
from meta_chat_exporter.models import ProfileMedia, Thread
from meta_chat_exporter.redaction import RedactionEngine
from meta_chat_exporter.safe_cache import load_cache, save_cache

logger = logging.getLogger(__name__)


class CacheService:
    """Serviço de cache separado da camada de interface.

    Encapsula a política de chave de cache e o wrapping de
    ``safe_cache.save_cache`` / ``safe_cache.load_cache``. Não possui qualquer
    dependência de PyQt nem realiza atualizações de interface — efeitos de UI
    (logs visuais) permanecem na GUI, que consome os valores retornados.
    """

    CACHE_DIR_NAME = ".chat_export_cache"

    def get_cache_key(self, html_files) -> str:
        """Gera chave de cache baseada nos arquivos (caminho + tamanho + modificação)."""
        parts = []
        for f in sorted(html_files, key=lambda x: str(x)):
            stat = f.stat()
            parts.append(f"{f}:{stat.st_size}:{stat.st_mtime_ns}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    def get_file_cache_key(self, html_file: Path) -> str:
        """Gera chave de cache para um único arquivo."""
        stat = html_file.stat()
        return hashlib.md5(f"{html_file}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()

    def get_cache_dir(self, html_files) -> Path:
        """Retorna (criando se necessário) o diretório de cache."""
        cache_dir = html_files[0].parent / self.CACHE_DIR_NAME
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    def get_cache_path(self, html_files) -> Path:
        """Retorna o caminho do arquivo de cache consolidado."""
        cache_dir = self.get_cache_dir(html_files)
        key = self.get_cache_key(html_files)
        return cache_dir / f"cache_{key}.json"

    def load_file_cache(self, html_file: Path, cache_dir: Path):
        """Carrega o cache de um único arquivo (ou ``None`` se ausente/erro)."""
        try:
            key = self.get_file_cache_key(html_file)
            cache_path = cache_dir / f"file_{key}.json"
            if cache_path.exists():
                return load_cache(cache_path)
        except Exception as e:
            logger.debug("Cache de arquivo não encontrado para %s: %s", html_file.name, e)
        return None

    def save_file_cache(self, html_file: Path, cache_dir: Path, data: dict) -> None:
        """Salva o cache de um único arquivo."""
        try:
            key = self.get_file_cache_key(html_file)
            cache_path = cache_dir / f"file_{key}.json"
            save_cache(cache_path, data)
        except Exception as e:
            logger.debug("Erro ao salvar cache de arquivo: %s", e)

    def load_from_cache(self, html_files):
        """Tenta carregar o resultado consolidado do cache (ou ``None``)."""
        try:
            cache_path = self.get_cache_path(html_files)
            if cache_path.exists():
                data = load_cache(cache_path)
                if data:
                    logger.info("Cache encontrado: %s", cache_path.name)
                    return data
        except Exception as e:
            logger.warning("Erro ao ler cache: %s", e)
        return None

    def save_to_cache(self, html_files, data) -> float | None:
        """Salva o resultado parseado no cache.

        Retorna o tamanho do cache em MB quando salvo com sucesso, ou ``None``
        em caso de erro. A GUI usa o valor retornado para registrar o log
        visual, preservando o comportamento observável.
        """
        try:
            cache_path = self.get_cache_path(html_files)
            save_cache(cache_path, data)
            size_mb = cache_path.stat().st_size / (1024 * 1024)
            logger.info("Cache salvo: %s (%.1f MB)", cache_path.name, size_mb)
            return size_mb
        except Exception as e:
            logger.warning("Erro ao salvar cache: %s", e)
            return None


class ExportService:
    """Serviço de exportação separado da camada de interface.

    Orquestra a geração de HTML (individual e unificado), JSON e CSV, incluindo
    o modo redigido. Não possui dependência de PyQt; a GUI cuida dos logs
    visuais, barras de progresso e diálogos, consumindo os caminhos retornados.
    """

    @staticmethod
    def _safe_thread_name(thread: Thread, owner_username: str) -> str:
        """Calcula um nome de arquivo seguro para um thread."""
        if thread.thread_name:
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", thread.thread_name)
        else:
            participants = [p[0] for p in thread.participants if p[0] != owner_username]
            safe_name = "_".join(participants[:3]) if participants else thread.thread_id
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)
        return safe_name

    @staticmethod
    def _redact_threads(
        threads: list[Thread],
        owner_username: str,
        profile_media: ProfileMedia | None = None,
    ) -> list[Thread]:
        """Aplica a redação uma única vez sobre uma cópia profunda da Data_Layer.

        Centraliza o ponto de redação (R4.1): copia os threads para não mutar o
        estado em memória da UI e delega ao `RedactionEngine`. A cópia já
        redigida é então consumida por qualquer exportador (HTML/JSON/CSV).
        """
        threads_redacted = copy.deepcopy(threads)
        RedactionEngine(owner_username).redact(threads_redacted, profile_media)
        return threads_redacted

    def export_thread_html(
        self,
        thread: Thread,
        owner_username: str,
        owner_id: str,
        transcriptions: dict,
        base_dir: Path,
        *,
        redact: bool = False,
        profile_media: ProfileMedia | None = None,
        source_files: list[Path] | None = None,
        write_manifest: bool = True,
    ) -> tuple[Path, str]:
        """Exporta um único thread para HTML. Retorna ``(output_path, filename)``.

        Quando ``redact`` é verdadeiro, a redação é aplicada sobre uma cópia
        profunda do thread (para não mutar o estado da UI) antes de gerar o HTML.
        O manifesto de custódia é gravado quando ``write_manifest`` é verdadeiro.
        """
        if redact:
            thread_for_gen = self._redact_threads([thread], owner_username, profile_media)[0]
        else:
            thread_for_gen = thread

        generator = ChatHTMLGenerator(thread_for_gen, owner_username, owner_id, transcriptions)

        safe_name = self._safe_thread_name(thread, owner_username)
        suffix = "_redigido" if redact else ""
        filename = f"chat{suffix}_{safe_name}_{thread.thread_id[-8:]}.html"
        output_path = thread.base_dir / filename if thread.base_dir else base_dir / filename

        generator.write_to_file(output_path)
        if write_manifest:
            self._write_custody_manifest(
                base_dir,
                [output_path],
                stem=f"manifesto_chat{suffix}",
                source_files=source_files,
            )
        return output_path, filename

    @staticmethod
    def _write_custody_manifest(
        base_dir: Path,
        output_files: list[Path],
        *,
        stem: str,
        source_files: list[Path] | None = None,
    ) -> Path | None:
        """Grava manifesto SHA-256 das fontes + saídas (F4). Falhas não abortam export."""
        try:
            return write_manifest_for_export(
                base_dir,
                source_files=source_files,
                output_files=output_files,
                stem=stem,
            )
        except Exception as e:
            logger.warning("Não foi possível gravar manifesto de custódia: %s", e)
            return None

    def export_all_html(
        self,
        threads_to_export: list[Thread],
        owner_username: str,
        owner_id: str,
        transcriptions: dict,
        profile_media: ProfileMedia,
        base_dir: Path,
        *,
        redact: bool = False,
        is_filtered: bool = False,
        source_files: list[Path] | None = None,
        write_manifest: bool = True,
    ) -> tuple[Path, str]:
        """Gera o HTML unificado de todas as conversas.

        Quando ``redact`` é verdadeiro, a redação é aplicada **uma única vez** na
        Data_Layer (sobre uma cópia profunda, para não mutar o estado da UI) e o
        gerador consome os dados já redigidos. Retorna ``(output_path, filename)``.
        """
        if redact:
            threads_for_gen = self._redact_threads(threads_to_export, owner_username, profile_media)
        else:
            threads_for_gen = threads_to_export

        generator = AllChatsHTMLGenerator(
            threads_for_gen,
            owner_username,
            owner_id,
            transcriptions,
            profile_media,
            base_dir=base_dir,
            redact=redact,
            already_redacted=redact,
        )

        suffix = "_redigido" if redact else ""
        prefix = "filtradas" if is_filtered else "todas_conversas"
        filename = f"{prefix}{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = base_dir / filename

        generator.write_to_file(output_path)
        if write_manifest:
            self._write_custody_manifest(
                base_dir,
                [output_path],
                stem=f"manifesto_{prefix}{suffix}",
                source_files=source_files,
            )
        return output_path, filename

    def export_json(
        self,
        threads_to_export: list[Thread],
        owner_username: str,
        owner_id: str,
        base_dir: Path,
        *,
        redact: bool = False,
        is_filtered: bool = False,
        source_files: list[Path] | None = None,
        write_manifest: bool = True,
    ) -> tuple[Path, str]:
        """Exporta as conversas para JSON (com estatísticas). Retorna ``(output_path, filename)``.

        Quando ``redact`` é verdadeiro, a Data_Layer é redigida uma única vez
        (sobre uma cópia profunda) antes de o exportador processar os dados.
        """
        if redact:
            threads_to_export = self._redact_threads(threads_to_export, owner_username)

        prefix = "filtradas" if is_filtered else "conversas"
        suffix = "_redigido" if redact else ""
        filename = f"{prefix}{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = base_dir / filename

        exporter = JSONExporter(threads_to_export, owner_username, owner_id, base_dir=base_dir)
        exporter.export(output_path, include_stats=True)
        if write_manifest:
            self._write_custody_manifest(
                base_dir,
                [output_path],
                stem=f"manifesto_{prefix}{suffix}",
                source_files=source_files,
            )
        return output_path, filename

    def export_csv(
        self,
        threads_to_export: list[Thread],
        owner_username: str,
        owner_id: str,
        base_dir: Path,
        *,
        redact: bool = False,
        is_filtered: bool = False,
        source_files: list[Path] | None = None,
        write_manifest: bool = True,
    ) -> tuple[Path, str, Path, str]:
        """Exporta as conversas para CSV e gera o CSV de estatísticas.

        Quando ``redact`` é verdadeiro, a Data_Layer é redigida uma única vez
        (sobre uma cópia profunda) antes de o exportador processar os dados.
        Retorna ``(output_path, filename, stats_path, stats_filename)``.
        """
        if redact:
            threads_to_export = self._redact_threads(threads_to_export, owner_username)

        prefix = "filtradas" if is_filtered else "conversas"
        suffix = "_redigido" if redact else ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}{suffix}_{timestamp}.csv"
        output_path = base_dir / filename

        exporter = CSVExporter(threads_to_export, owner_username, owner_id, base_dir=base_dir)
        exporter.export(output_path)

        stats_filename = f"{prefix}{suffix}_{timestamp}_stats.csv"
        stats_path = base_dir / stats_filename
        exporter.export_stats(stats_path)

        if write_manifest:
            self._write_custody_manifest(
                base_dir,
                [output_path, stats_path],
                stem=f"manifesto_{prefix}{suffix}",
                source_files=source_files,
            )
        return output_path, filename, stats_path, stats_filename
