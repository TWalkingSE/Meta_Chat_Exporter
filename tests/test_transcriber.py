import builtins
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from meta_chat_exporter import transcriber
from meta_chat_exporter.transcriber import (
    AudioTranscriber,
    check_transcription_environment,
    check_whisper_available,
    detect_gpu,
    format_gpu_info,
    start_transcription_subprocess,
)


class TestTranscriberDependencies(unittest.TestCase):
    def test_check_whisper_available_reports_torch_runtime_error(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise RuntimeError("torch quebrado")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            available, message = check_whisper_available()

        self.assertFalse(available)
        self.assertIn("Erro ao carregar PyTorch", message)
        self.assertIn("torch quebrado", message)

    def test_check_whisper_available_reports_missing_ffmpeg(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in {"torch", "whisper"}:
                return SimpleNamespace()
            return real_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=fake_import),
            patch.object(transcriber.shutil, "which", return_value=None),
        ):
            available, message = check_whisper_available()

        self.assertFalse(available)
        self.assertIn("FFmpeg não encontrado", message)

    def test_check_whisper_available_accepts_required_dependencies(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name in {"torch", "whisper"}:
                return SimpleNamespace()
            return real_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=fake_import),
            patch.object(transcriber.shutil, "which", return_value="C:/ffmpeg/bin/ffmpeg.exe"),
        ):
            available, message = check_whisper_available()

        self.assertTrue(available)
        self.assertEqual(message, "Whisper disponível")

    def test_load_model_rejects_forced_cuda_when_unavailable(self):
        fake_whisper = SimpleNamespace(load_model=lambda *args, **kwargs: None)
        fake_gpu = {"device": "cpu", "name": "CPU", "vram_total_str": "N/A"}

        with (
            patch.dict(sys.modules, {"whisper": fake_whisper}),
            patch.object(transcriber, "detect_gpu", return_value=fake_gpu),
        ):
            audio_transcriber = AudioTranscriber(device="cuda")
            with self.assertRaisesRegex(RuntimeError, "GPU CUDA não disponível"):
                audio_transcriber._load_model()

    def test_detect_gpu_reports_nvidia_with_cpu_only_torch(self):
        fake_torch = SimpleNamespace(
            __version__="2.12.1+cpu",
            version=SimpleNamespace(cuda=None),
            cuda=SimpleNamespace(is_available=lambda: False),
        )
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="NVIDIA RTX 4500 Ada Generation, 24570\n",
            stderr="",
        )

        with (
            patch.dict(sys.modules, {"torch": fake_torch}),
            patch.object(transcriber.subprocess, "run", return_value=completed),
        ):
            gpu_info = detect_gpu()

        self.assertFalse(gpu_info["available"])
        self.assertTrue(gpu_info["nvidia_available"])
        self.assertEqual(gpu_info["device"], "cpu")
        self.assertEqual(gpu_info["nvidia_name"], "NVIDIA RTX 4500 Ada Generation")
        self.assertEqual(gpu_info["torch_cuda_version"], "CPU-only")
        self.assertIn("CPU-only", format_gpu_info(gpu_info))

    def test_check_transcription_environment_reads_subprocess_json(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "aviso qualquer\n"
                '{"available": true, "message": "ok", "gpu_info": '
                '{"device": "cpu", "recommended_model": "tiny"}}\n'
            ),
            stderr="",
        )

        with patch.object(transcriber.subprocess, "run", return_value=completed):
            available, message, gpu_info = check_transcription_environment()

        self.assertTrue(available)
        self.assertEqual(message, "ok")
        self.assertEqual(gpu_info["device"], "cpu")

    def test_check_transcription_environment_handles_subprocess_failure(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=3221225477,
            stdout="",
            stderr="falha nativa",
        )

        with patch.object(transcriber.subprocess, "run", return_value=completed):
            available, message, gpu_info = check_transcription_environment()

        self.assertFalse(available)
        self.assertIn("processo isolado", message)
        self.assertIn("falha nativa", message)
        self.assertEqual(gpu_info["device"], "cpu")

    def test_start_transcription_subprocess_rejects_invalid_audio_folder(self):
        with self.assertRaises(FileNotFoundError):
            start_transcription_subprocess(
                model_name="tiny",
                language="pt",
                device="cpu",
                cache_dir="",
                audio_folder="Z:/pasta_inexistente_xyz",
                force_retranscribe=False,
            )


if __name__ == "__main__":
    unittest.main()
