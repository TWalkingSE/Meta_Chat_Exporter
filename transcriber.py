"""
Meta Platforms Chat Exporter - Transcrição Automática de Áudios
Utiliza OpenAI Whisper para transcrição local (CPU ou GPU CUDA)
"""

import json
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Extensões de áudio suportadas
AUDIO_EXTENSIONS = {".mp3", ".aac", ".ogg", ".wav", ".m4a", ".wma", ".flac", ".opus"}

# Modelos disponíveis do Whisper com requisitos
WHISPER_MODELS = {
    "tiny":     {"vram_mb": 1000,  "label": "Tiny (~1GB)",     "desc": "Mais rápido, menor qualidade"},
    "base":     {"vram_mb": 1500,  "label": "Base (~1.5GB)",   "desc": "Bom equilíbrio velocidade/qualidade"},
    "small":    {"vram_mb": 2500,  "label": "Small (~2.5GB)",  "desc": "Boa qualidade, GPU recomendada"},
    "medium":   {"vram_mb": 5000,  "label": "Medium (~5GB)",   "desc": "Alta qualidade, requer GPU"},
    "large-v2": {"vram_mb": 10000, "label": "Large-v2 (~10GB)", "desc": "Excelente qualidade, GPU potente"},
    "large-v3": {"vram_mb": 10000, "label": "Large-v3 (~10GB)", "desc": "Melhor qualidade disponível, GPU potente"},
}


def check_whisper_available() -> Tuple[bool, str]:
    """
    Verifica se whisper e torch estão instalados.
    Retorna (disponível, mensagem).
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, (
            "PyTorch não encontrado.\n\n"
            "Instale com:\n"
            "  pip install torch torchvision torchaudio\n\n"
            "Para GPU NVIDIA (CUDA), instale a versão correta em:\n"
            "  https://pytorch.org/get-started/locally/"
        )

    try:
        import whisper  # noqa: F401
    except ImportError:
        return False, (
            "OpenAI Whisper não encontrado.\n\n"
            "Instale com:\n"
            "  pip install openai-whisper"
        )

    return True, "Whisper disponível"


def detect_gpu() -> Dict[str, object]:
    """
    Detecta a GPU disponível e retorna informações.
    Retorna dict com: available, name, vram_mb, vram_total_str, recommended_model
    """
    info = {
        "available": False,
        "name": "Nenhuma GPU CUDA detectada",
        "vram_mb": 0,
        "vram_total_str": "N/A",
        "recommended_model": "tiny",
        "device": "cpu",
    }

    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["device"] = "cuda"
            info["name"] = torch.cuda.get_device_name(0)

            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_mb = vram_bytes / (1024 * 1024)
            info["vram_mb"] = int(vram_mb)

            if vram_mb >= 1024:
                info["vram_total_str"] = f"{vram_mb / 1024:.1f} GB"
            else:
                info["vram_total_str"] = f"{int(vram_mb)} MB"

            # Recomendar modelo baseado na VRAM (deixar margem de ~20%)
            usable_vram = vram_mb * 0.8
            if usable_vram >= 10000:
                info["recommended_model"] = "large-v3"
            elif usable_vram >= 5000:
                info["recommended_model"] = "medium"
            elif usable_vram >= 2500:
                info["recommended_model"] = "small"
            elif usable_vram >= 1500:
                info["recommended_model"] = "base"
            else:
                info["recommended_model"] = "tiny"
        else:
            info["name"] = "CPU (sem GPU CUDA)"
            info["recommended_model"] = "tiny"
    except ImportError:
        info["name"] = "PyTorch não instalado"
    except Exception as e:
        info["name"] = f"Erro ao detectar GPU: {e}"
        logger.warning("Erro ao detectar GPU: %s", e)

    return info


def scan_audio_files(folder: Path) -> List[Path]:
    """
    Escaneia uma pasta (e subpastas) procurando arquivos de áudio.
    Retorna lista de Paths dos arquivos de áudio encontrados.
    """
    audio_files = []

    if not folder.exists():
        return audio_files

    for ext in AUDIO_EXTENSIONS:
        for f in sorted(folder.rglob(f"*{ext}")):
            if f.is_file():
                audio_files.append(f)

    audio_files.sort()

    return audio_files


def _file_hash(filepath: Path) -> str:
    """Calcula hash MD5 do arquivo para cache."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class TranscriptionCache:
    """Gerencia cache de transcrições para evitar retranscrever áudios."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "transcriptions"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "transcription_cache.json"
        self._cache: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """Carrega o cache do disco."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info("Cache de transcrições carregado: %d entradas", len(self._cache))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Erro ao carregar cache de transcrições: %s", e)
                self._cache = {}

    def _save(self):
        """Salva o cache no disco."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("Erro ao salvar cache de transcrições: %s", e)

    def get(self, filepath: Path) -> Optional[str]:
        """
        Retorna transcrição cacheada se existir e o arquivo não tiver mudado.
        """
        key = str(filepath.resolve())
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Verificar se o arquivo mudou (por tamanho — hash é lento para muitos arquivos)
        try:
            current_size = filepath.stat().st_size
            if current_size == entry.get("size"):
                return entry.get("text")
        except OSError:
            pass

        return None

    def put(self, filepath: Path, text: str, model: str, language: str):
        """Armazena transcrição no cache."""
        key = str(filepath.resolve())
        try:
            size = filepath.stat().st_size
        except OSError:
            size = 0

        self._cache[key] = {
            "text": text,
            "size": size,
            "model": model,
            "language": language,
            "filename": filepath.name,
        }
        self._save()

    def count(self) -> int:
        return len(self._cache)

    def get_all_as_dict(self) -> Dict[str, str]:
        """
        Retorna todas as transcrições como {filename_lower: text}.
        Compatível com o sistema de transcrições existente.
        """
        result = {}
        for entry in self._cache.values():
            filename = entry.get("filename", "")
            text = entry.get("text", "")
            if filename and text:
                # Adicionar com nome completo e sem extensão, em lowercase
                result[filename.lower()] = text
                name_no_ext = filename.rsplit(".", 1)[0].lower() if "." in filename else filename.lower()
                result[name_no_ext] = text
        return result


class AudioTranscriber:
    """
    Transcritor de áudio usando OpenAI Whisper.
    Suporta GPU (CUDA) e CPU, com cache e progresso.
    """

    def __init__(
        self,
        model_name: str = "base",
        language: str = "pt",
        device: str = "auto",
        cache_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            model_name: Nome do modelo Whisper (tiny, base, small, medium, large-v2, large-v3)
            language: Código do idioma (pt, en, es, ou None para auto-detectar)
            cache_dir: Diretório para cache (default: .chat_export_cache na pasta dos áudios)
            progress_callback: Chamado com (current, total, filename, status)
            log_callback: Chamado com mensagens de log
        """
        self.model_name = model_name
        self.language = language
        self.device = device
        self.cache_dir = cache_dir
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._model = None
        self._cancelled = False

    def _log(self, message: str):
        """Envia mensagem de log."""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def cancel(self):
        """Sinaliza cancelamento da transcrição."""
        self._cancelled = True

    def _load_model(self):
        """Carrega o modelo Whisper."""
        import whisper

        gpu_info = detect_gpu()
        device_to_use = self.device if self.device != "auto" else gpu_info["device"]

        self._log(f"🔧 Carregando modelo Whisper '{self.model_name}'...")
        if self.device == "auto":
            self._log(f"   Dispositivo: {gpu_info['name']}")
        else:
            self._log(f"   Dispositivo: {device_to_use.upper()} (forçado pelo usuário)")

        if device_to_use == "cuda" and gpu_info["device"] == "cuda":
            self._log(f"   VRAM: {gpu_info['vram_total_str']}")

        start = time.time()
        self._model = whisper.load_model(self.model_name, device=device_to_use)
        elapsed = time.time() - start
        self._log(f"   Modelo carregado em {elapsed:.1f}s")

    def transcribe_folder(
        self,
        audio_folder: Path,
        force_retranscribe: bool = False,
    ) -> Dict[str, str]:
        """
        Transcreve todos os áudios de uma pasta.

        Args:
            audio_folder: Pasta contendo os áudios
            force_retranscribe: Se True, ignora o cache

        Returns:
            Dict {filename_lower: transcription_text}
        """
        self._cancelled = False

        # Escanear áudios
        audio_files = scan_audio_files(audio_folder)
        if not audio_files:
            self._log("⚠️ Nenhum arquivo de áudio encontrado na pasta")
            return {}

        self._log(f"🔍 {len(audio_files)} arquivo(s) de áudio encontrado(s)")

        # Inicializar cache
        cache_path = self.cache_dir or (audio_folder.parent / ".chat_export_cache")
        cache = TranscriptionCache(cache_path)

        # Separar já cacheados dos pendentes
        to_transcribe = []
        results: Dict[str, str] = {}

        for af in audio_files:
            if not force_retranscribe:
                cached = cache.get(af)
                if cached:
                    fname = af.name.lower()
                    results[fname] = cached
                    name_no_ext = fname.rsplit(".", 1)[0] if "." in fname else fname
                    results[name_no_ext] = cached
                    continue
            to_transcribe.append(af)

        cached_count = len(audio_files) - len(to_transcribe)
        if cached_count > 0:
            self._log(f"✅ {cached_count} áudio(s) já transcritos (cache)")

        if not to_transcribe:
            self._log("✅ Todos os áudios já foram transcritos anteriormente")
            return cache.get_all_as_dict()

        self._log(f"🎙️ {len(to_transcribe)} áudio(s) para transcrever")

        # Carregar modelo
        self._load_model()

        # Transcrever cada áudio
        total = len(to_transcribe)
        success_count = 0
        error_count = 0
        start_total = time.time()

        for i, audio_path in enumerate(to_transcribe, 1):
            if self._cancelled:
                self._log(f"⏹️ Transcrição cancelada pelo usuário ({i - 1}/{total})")
                break

            filename = audio_path.name
            if self.progress_callback:
                self.progress_callback(i, total, filename, "transcrevendo")

            self._log(f"🎙️ [{i}/{total}] {filename}")

            try:
                start_file = time.time()

                # Opções de transcrição
                options = {
                    "fp16": self._model.device.type == "cuda",
                    "verbose": False,
                }
                if self.language:
                    options["language"] = self.language

                result = self._model.transcribe(str(audio_path), **options)
                text = result.get("text", "").strip()
                elapsed_file = time.time() - start_file

                if text:
                    # Salvar no cache
                    cache.put(audio_path, text, self.model_name, self.language or "auto")

                    # Adicionar aos resultados
                    fname = filename.lower()
                    results[fname] = text
                    name_no_ext = fname.rsplit(".", 1)[0] if "." in fname else fname
                    results[name_no_ext] = text

                    success_count += 1
                    # Mostrar preview da transcrição (truncada)
                    preview = text[:80] + "..." if len(text) > 80 else text
                    self._log(f"   ✅ ({elapsed_file:.1f}s) {preview}")
                else:
                    self._log(f"   ⚠️ ({elapsed_file:.1f}s) Áudio sem fala detectada")
                    success_count += 1

            except Exception as e:
                error_count += 1
                self._log(f"   ❌ Erro: {e}")
                logger.exception("Erro ao transcrever %s", audio_path)

        elapsed_total = time.time() - start_total

        # Resumo final
        self._log("━" * 35)
        self._log(f"🏁 Transcrição concluída em {elapsed_total:.0f}s")
        self._log(f"   ✅ Sucesso: {success_count}")
        if cached_count > 0:
            self._log(f"   📦 Cache: {cached_count}")
        if error_count > 0:
            self._log(f"   ❌ Erros: {error_count}")
        self._log(f"   📝 Total de transcrições: {len(results) // 2}")

        if self.progress_callback:
            self.progress_callback(total, total, "", "concluído")

        return results


def get_suggested_model(gpu_info: dict) -> str:
    """Retorna o modelo sugerido baseado no hardware detectado."""
    return gpu_info.get("recommended_model", "tiny")


def format_gpu_info(gpu_info: dict) -> str:
    """Formata informações da GPU para exibição ao usuário."""
    lines = []
    if gpu_info["available"]:
        lines.append(f"🟢 GPU Detectada: {gpu_info['name']}")
        lines.append(f"   VRAM: {gpu_info['vram_total_str']}")
        lines.append(f"   Modelo sugerido: {WHISPER_MODELS[gpu_info['recommended_model']]['label']}")
    else:
        lines.append(f"🟡 Padrão: {gpu_info['name']}")
        lines.append("   Sem GPU detectada automaticamente (você pode forçar abaixo, se tiver certeza).")
        lines.append(f"   Modelo sugerido: {WHISPER_MODELS['tiny']['label']}")
    return "\n".join(lines)
