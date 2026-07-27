"""
Meta Platforms Chat Exporter - Transcrição Automática de Áudios
Utiliza OpenAI Whisper para transcrição local (CPU ou GPU CUDA)
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


def _default_gpu_info() -> dict[str, object]:
    return {
        "available": False,
        "name": "CPU (verificação segura)",
        "vram_mb": 0,
        "vram_total_str": "N/A",
        "recommended_model": "tiny",
        "device": "cpu",
        "nvidia_available": False,
        "nvidia_name": "",
        "torch_version": "",
        "torch_cuda_version": "",
        "cuda_issue": "",
    }


def _format_vram_mb(vram_mb: int | float) -> str:
    if vram_mb >= 1024:
        return f"{vram_mb / 1024:.1f} GB"
    return f"{int(vram_mb)} MB"


def _recommend_model_for_vram(vram_mb: int | float) -> str:
    usable_vram = vram_mb * 0.8
    if usable_vram >= 10000:
        return "large-v3"
    if usable_vram >= 5000:
        return "medium"
    if usable_vram >= 2500:
        return "small"
    if usable_vram >= 1500:
        return "base"
    return "tiny"


def _detect_nvidia_gpu() -> dict[str, object] | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
    if not first_line or "," not in first_line:
        return None

    name, memory = [part.strip() for part in first_line.split(",", 1)]
    try:
        vram_mb = int(float(memory))
    except ValueError:
        vram_mb = 0

    return {"name": name, "vram_mb": vram_mb}


# Extensões de áudio suportadas
AUDIO_EXTENSIONS = {".mp3", ".aac", ".ogg", ".wav", ".m4a", ".wma", ".flac", ".opus"}

# Modelos disponíveis do Whisper com requisitos
WHISPER_MODELS = {
    "tiny": {"vram_mb": 1000, "label": "Tiny (~1GB)", "desc": "Mais rápido, menor qualidade"},
    "base": {
        "vram_mb": 1500,
        "label": "Base (~1.5GB)",
        "desc": "Bom equilíbrio velocidade/qualidade",
    },
    "small": {"vram_mb": 2500, "label": "Small (~2.5GB)", "desc": "Boa qualidade, GPU recomendada"},
    "medium": {"vram_mb": 5000, "label": "Medium (~5GB)", "desc": "Alta qualidade, requer GPU"},
    "large-v2": {
        "vram_mb": 10000,
        "label": "Large-v2 (~10GB)",
        "desc": "Excelente qualidade, GPU potente",
    },
    "large-v3": {
        "vram_mb": 10000,
        "label": "Large-v3 (~10GB)",
        "desc": "Melhor qualidade disponível, GPU potente",
    },
}


def check_whisper_available() -> tuple[bool, str]:
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
    except Exception as e:
        logger.exception("Erro ao importar PyTorch")
        return False, f"Erro ao carregar PyTorch:\n{e}"

    try:
        import whisper  # noqa: F401
    except ImportError:
        return False, (
            "OpenAI Whisper não encontrado.\n\n" "Instale com:\n" "  pip install openai-whisper"
        )
    except Exception as e:
        logger.exception("Erro ao importar OpenAI Whisper")
        return False, f"Erro ao carregar OpenAI Whisper:\n{e}"

    if shutil.which("ffmpeg") is None:
        return False, (
            "FFmpeg não encontrado.\n\n"
            "O Whisper precisa do ffmpeg disponível no PATH para ler os áudios.\n"
            "Instale o FFmpeg e reabra a aplicação antes de transcrever."
        )

    return True, "Whisper disponível"


def pre_import_transcription_modules() -> None:
    """Importa torch e whisper na thread chamadora.

    Importar essas bibliotecas (C extensions pesadas) de uma thread
    de background no Windows pode causar crash nativo do processo.
    Chamar esta função na thread principal antes de iniciar a thread
    de transcrição garante que os módulos sejam carregados com segurança.
    """
    import torch  # noqa: F401
    import whisper  # noqa: F401


_TRANSCRIPTION_SCRIPT = r"""
import json, sys, os, traceback
from pathlib import Path

def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)

try:
    params = json.loads(sys.stdin.read())
    from meta_chat_exporter.transcriber import AudioTranscriber

    def progress_cb(current, total, filename, status):
        emit({"type": "progress", "current": current, "total": total,
              "filename": filename, "status": status})

    def log_cb(msg):
        emit({"type": "log", "message": msg})

    t = AudioTranscriber(
        model_name=params["model_name"],
        language=params["language"],
        device=params["device"],
        cache_dir=Path(params["cache_dir"]) if params.get("cache_dir") else None,
        progress_callback=progress_cb,
        log_callback=log_cb,
    )

    results = t.transcribe_folder(
        Path(params["audio_folder"]),
        force_retranscribe=params.get("force_retranscribe", False),
    )
    emit({"type": "results", "data": results})
except BaseException as e:
    emit({"type": "error", "message": str(e), "traceback": traceback.format_exc()})
    sys.exit(1)
"""


def start_transcription_subprocess(
    model_name: str,
    language: str,
    device: str,
    cache_dir: str,
    audio_folder: str,
    force_retranscribe: bool,
) -> subprocess.Popen:
    """Inicia a transcrição em um subprocesso isolado.

    Retorna o Popen. Leia stdout linha a linha para eventos JSON:
    - {"type": "log", "message": "..."}
    - {"type": "progress", "current": N, "total": N, "filename": "...", "status": "..."}
    - {"type": "results", "data": {...}}
    - {"type": "error", "message": "...", "traceback": "..."}

    Para cancelar, chame .terminate() no Popen.

    Raises:
        FileNotFoundError: se ``audio_folder`` não existir ou não for diretório.
        OSError: se o subprocesso não puder ser iniciado.
    """
    audio_path = Path(audio_folder)
    if not audio_path.is_dir():
        raise FileNotFoundError(f"Pasta de áudios inválida: {audio_folder}")

    cache_path = Path(cache_dir) if cache_dir else (audio_path / ".chat_export_cache")
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Não foi possível criar diretório de cache: {cache_path}") from e

    params = json.dumps({
        "model_name": model_name,
        "language": language,
        "device": device,
        "cache_dir": str(cache_path),
        "audio_folder": str(audio_path),
        "force_retranscribe": force_retranscribe,
    })

    env = os.environ.copy()
    package_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    # stderr é redirecionado para stdout para evitar deadlock: warnings do
    # PyTorch/Whisper podem encher o pipe de stderr e travar o subprocesso,
    # já que a GUI só lê stderr no final. Linhas não-JSON em stdout são
    # silenciosamente ignoradas pela GUI. proc.stderr fica None.
    proc = subprocess.Popen(
        [sys.executable, "-c", _TRANSCRIPTION_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.stdin is not None
    proc.stdin.write(params)
    proc.stdin.close()
    return proc


def detect_gpu() -> dict[str, object]:
    """
    Detecta a GPU disponível e retorna informações.
    Retorna dict com: available, name, vram_mb, vram_total_str, recommended_model
    """
    info = _default_gpu_info()
    info["name"] = "Nenhuma GPU CUDA detectada"
    nvidia_gpu = _detect_nvidia_gpu()

    try:
        import torch

        info["torch_version"] = getattr(torch, "__version__", "")
        torch_cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
        info["torch_cuda_version"] = torch_cuda_version or "CPU-only"

        if torch.cuda.is_available():
            info["available"] = True
            info["device"] = "cuda"
            info["name"] = torch.cuda.get_device_name(0)
            info["nvidia_available"] = True
            info["nvidia_name"] = str(info["name"])

            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_mb = vram_bytes / (1024 * 1024)
            info["vram_mb"] = int(vram_mb)
            info["vram_total_str"] = _format_vram_mb(vram_mb)
            info["recommended_model"] = _recommend_model_for_vram(vram_mb)
        elif nvidia_gpu:
            vram_mb = int(cast(Any, nvidia_gpu.get("vram_mb", 0)) or 0)
            cuda_issue = "PyTorch instalado é CPU-only"
            if torch_cuda_version:
                cuda_issue = "CUDA não inicializou no PyTorch"
            info.update(
                {
                    "name": f"{nvidia_gpu['name']} (CUDA indisponível no PyTorch)",
                    "nvidia_available": True,
                    "nvidia_name": str(nvidia_gpu["name"]),
                    "vram_mb": vram_mb,
                    "vram_total_str": _format_vram_mb(vram_mb) if vram_mb else "N/A",
                    "recommended_model": _recommend_model_for_vram(vram_mb),
                    "cuda_issue": cuda_issue,
                }
            )
        else:
            info["name"] = "CPU (sem GPU NVIDIA/CUDA detectada)"
            info["recommended_model"] = "tiny"
    except ImportError:
        if nvidia_gpu:
            vram_mb = int(cast(Any, nvidia_gpu.get("vram_mb", 0)) or 0)
            info.update(
                {
                    "name": f"{nvidia_gpu['name']} (PyTorch não instalado)",
                    "nvidia_available": True,
                    "nvidia_name": str(nvidia_gpu["name"]),
                    "vram_mb": vram_mb,
                    "vram_total_str": _format_vram_mb(vram_mb) if vram_mb else "N/A",
                    "recommended_model": _recommend_model_for_vram(vram_mb),
                    "cuda_issue": "PyTorch não instalado",
                }
            )
        else:
            info["name"] = "PyTorch não instalado"
    except Exception as e:
        info["name"] = f"Erro ao detectar GPU: {e}"
        logger.warning("Erro ao detectar GPU: %s", e)
        if nvidia_gpu:
            info["nvidia_available"] = True
            info["nvidia_name"] = str(nvidia_gpu["name"])

    return info


def check_transcription_environment(timeout_seconds: int = 30) -> tuple[bool, str, dict[str, object]]:
    # Quando rodando como exe PyInstaller, sys.executable é o próprio exe,
    # não um interpretador Python. Usar import direto com tratamento de erros.
    if getattr(sys, "frozen", False):
        try:
            available, message = check_whisper_available()
            gpu_info = detect_gpu() if available else _default_gpu_info()
            return available, message, gpu_info
        except Exception as e:
            logger.exception("Erro ao verificar ambiente de transcrição (frozen)")
            return False, f"Erro ao verificar dependências de transcrição:\n{e}", _default_gpu_info()

    script = (
        "import json, traceback\n"
        "try:\n"
        "    from meta_chat_exporter.transcriber import check_whisper_available, detect_gpu\n"
        "    available, message = check_whisper_available()\n"
        "    gpu_info = detect_gpu() if available else {}\n"
        "    print(json.dumps({\"available\": available, \"message\": message, "
        "\"gpu_info\": gpu_info}, ensure_ascii=False))\n"
        "except BaseException as e:\n"
        "    print(json.dumps({\"available\": False, \"message\": str(e), "
        "\"traceback\": traceback.format_exc(), \"gpu_info\": {}}, ensure_ascii=False))\n"
        "    raise\n"
    )
    env = os.environ.copy()
    package_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = package_root + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Tempo esgotado ao verificar Whisper/PyTorch.", _default_gpu_info()
    except OSError as e:
        return False, f"Erro ao iniciar verificação de transcrição:\n{e}", _default_gpu_info()

    stdout_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    data = None
    if stdout_lines:
        try:
            data = json.loads(stdout_lines[-1])
        except json.JSONDecodeError:
            data = None

    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip()
        if data and data.get("message"):
            details = str(data["message"])
        if len(details) > 1200:
            details = details[:1200] + "..."
        return (
            False,
            "A verificação de Whisper/PyTorch falhou em processo isolado.\n\n" + details,
            _default_gpu_info(),
        )

    if not isinstance(data, dict):
        details = completed.stderr.strip() or completed.stdout.strip() or "Sem saída da verificação."
        if len(details) > 1200:
            details = details[:1200] + "..."
        return False, "Não foi possível interpretar a verificação de transcrição.\n\n" + details, _default_gpu_info()

    raw_gpu = data.get("gpu_info")
    resolved_gpu: dict[str, object]
    if isinstance(raw_gpu, dict) and raw_gpu:
        resolved_gpu = cast(dict[str, object], raw_gpu)
    else:
        resolved_gpu = _default_gpu_info()
    return bool(data.get("available")), str(data.get("message", "")), resolved_gpu


def scan_audio_files(folder: Path) -> list[Path]:
    """
    Escaneia uma pasta (e subpastas) procurando arquivos de áudio.
    Retorna lista de Paths dos arquivos de áudio encontrados.
    """
    audio_files: list[Path] = []

    if not folder.exists():
        return audio_files

    for ext in AUDIO_EXTENSIONS:
        for f in sorted(folder.rglob(f"*{ext}")):
            if f.is_file():
                audio_files.append(f)

    audio_files.sort()

    return audio_files


class TranscriptionCache:
    """Gerencia cache de transcrições para evitar retranscrever áudios."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir / "transcriptions"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "transcription_cache.json"
        self._cache: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Carrega o cache do disco."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
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

    def get(self, filepath: Path) -> str | None:
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

    def get_all_as_dict(self) -> dict[str, str]:
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
                name_no_ext = (
                    filename.rsplit(".", 1)[0].lower() if "." in filename else filename.lower()
                )
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
        cache_dir: Path | None = None,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
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
        self._model: Any | None = None
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
        raw_device = self.device if self.device != "auto" else gpu_info["device"]
        device_to_use = str(raw_device)
        if device_to_use == "cuda" and gpu_info["device"] != "cuda":
            if gpu_info.get("nvidia_available"):
                raise RuntimeError(
                    "GPU NVIDIA detectada, mas o PyTorch deste venv não tem CUDA ativo. "
                    "Reinstale o PyTorch com suporte CUDA antes de selecionar GPU."
                )
            raise RuntimeError(
                "GPU CUDA não disponível para o PyTorch atual. "
                "Selecione CPU ou instale o PyTorch com suporte a CUDA."
            )

        self._log(f"🔧 Carregando modelo Whisper '{self.model_name}'...")
        if self.progress_callback:
            self.progress_callback(0, 1, "", "carregando modelo")

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
        if self.progress_callback:
            self.progress_callback(1, 1, "", "modelo pronto")

    def transcribe_folder(
        self,
        audio_folder: Path,
        force_retranscribe: bool = False,
    ) -> dict[str, str]:
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
        results: dict[str, str] = {}

        for idx, af in enumerate(audio_files, 1):
            _idx, _total, _name = idx, len(audio_files), af.name
            if self.progress_callback:
                self.progress_callback(_idx, _total, _name, "verificando cache")
            if not force_retranscribe:
                cached = cache.get(af)
                if cached:
                    fname = af.name.lower()
                    results[fname] = cached
                    name_no_ext = fname.rsplit(".", 1)[0] if "." in fname else fname
                    results[name_no_ext] = cached
                    if self.progress_callback:
                        self.progress_callback(_idx, _total, _name, "cache")
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
            i_total, i_current = total, i
            if self.progress_callback:
                self.progress_callback(i_current, i_total, filename, "iniciando")

            self._log(f"🎙️ [{i_current}/{i_total}] {filename}")

            try:
                start_file = time.time()
                if self.progress_callback:
                    self.progress_callback(i_current, i_total, filename, "transcrevendo")

                model = self._model
                if model is None:
                    raise RuntimeError("Modelo Whisper não carregado")

                # Opções de transcrição
                options = {
                    "fp16": model.device.type == "cuda",
                    "verbose": False,
                }
                if self.language:
                    options["language"] = self.language

                # Watchdog: emite um pulso de progresso a cada 2 segundos
                # enquanto o Whisper processa o arquivo, para a GUI não parecer travada.
                keep_alive_stop = threading.Event()
                def _keep_alive(_i=i_current, _total=i_total, _fname=filename, _stop=keep_alive_stop):
                    while not _stop.wait(2.0):
                        if self.progress_callback:
                            self.progress_callback(_i, _total, _fname, "processando")
                keep_alive_thread = threading.Thread(target=_keep_alive, daemon=True)
                keep_alive_thread.start()

                try:
                    result = model.transcribe(str(audio_path), **options)
                finally:
                    keep_alive_stop.set()
                    keep_alive_thread.join(timeout=0.5)

                if self.progress_callback:
                    self.progress_callback(i_current, i_total, filename, "transcrevendo")

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
            final_status = "cancelado" if self._cancelled else "concluído"
            self.progress_callback(total, total, "", final_status)

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
        lines.append(
            f"   Modelo sugerido: {WHISPER_MODELS[gpu_info['recommended_model']]['label']}"
        )
    elif gpu_info.get("nvidia_available"):
        recommended = gpu_info.get("recommended_model", "tiny")
        lines.append(f"� GPU NVIDIA detectada: {gpu_info.get('nvidia_name') or gpu_info['name']}")
        lines.append(f"   VRAM: {gpu_info['vram_total_str']}")
        lines.append(f"   Status: {gpu_info.get('cuda_issue') or 'CUDA indisponível no PyTorch'}")
        if gpu_info.get("torch_version"):
            lines.append(f"   PyTorch: {gpu_info['torch_version']} ({gpu_info['torch_cuda_version']})")
        lines.append(f"   Modelo sugerido após corrigir CUDA: {WHISPER_MODELS[recommended]['label']}")
        lines.append("   Para usar GPU, reinstale PyTorch com CUDA no venv.")
    else:
        lines.append(f"🟡 Padrão: {gpu_info['name']}")
        lines.append("   Sem GPU NVIDIA/CUDA detectada automaticamente.")
        lines.append(f"   Modelo sugerido: {WHISPER_MODELS['tiny']['label']}")
    return "\n".join(lines)
