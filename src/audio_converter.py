import os
import shutil
import subprocess
from pathlib import Path


class AudioConverterError(Exception):
    pass


class AudioConverter:
    """Конвертирует голосовые Telegram (OGG/Opus) для OpenRouter (MP3) и Ollama (WAV)."""

    @staticmethod
    def telegram_voice_to_mp3(ogg_bytes: bytes) -> bytes:
        return AudioConverter._convert(ogg_bytes, ["-f", "mp3"])

    @staticmethod
    def telegram_voice_to_wav(ogg_bytes: bytes) -> bytes:
        return AudioConverter._convert(
            ogg_bytes, ["-ar", "16000", "-ac", "1", "-f", "wav"]
        )

    @staticmethod
    def _convert(ogg_bytes: bytes, output_args: list[str]) -> bytes:
        ffmpeg = AudioConverter._resolve_ffmpeg()
        try:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    *output_args,
                    "pipe:1",
                ],
                input=ogg_bytes,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise AudioConverterError(
                "ffmpeg не найден — установите ffmpeg для обработки голосовых"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace").strip()
            raise AudioConverterError(
                f"не удалось конвертировать аудио: {stderr or exc}"
            ) from exc

        if not result.stdout:
            raise AudioConverterError("ffmpeg вернул пустой результат")

        return result.stdout

    @staticmethod
    def _resolve_ffmpeg() -> str:
        configured = os.getenv("FFMPEG_PATH", "").strip()
        if configured:
            path = Path(configured)
            if path.is_file():
                return str(path)
            raise AudioConverterError(f"FFMPEG_PATH не найден: {configured}")

        home = Path.home()
        candidates = [
            home / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe",
            home / "scoop" / "shims" / "ffmpeg.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        found = shutil.which("ffmpeg")
        if found:
            return found

        raise AudioConverterError(
            "ffmpeg не найден — установите ffmpeg (scoop install ffmpeg) "
            "или задайте FFMPEG_PATH"
        )
