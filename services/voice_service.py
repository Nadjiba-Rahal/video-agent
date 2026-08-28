"""
Text-to-speech provider used to synthesize scene narration.

Kept as a small strategy-pattern (`BaseVoiceProvider`) so a different
provider can be swapped in later without touching the pipeline code
that calls it.
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Optional

from config.settings import settings
from utils.logger import get_logger

log = get_logger(__name__)


def _get_audio_duration_seconds(file_path: str) -> float:
    """Reads the exact duration of an audio file via ffprobe.

    Falls back to a conservative default if ffprobe isn't available or
    the file can't be read, so a measurement failure never crashes the
    pipeline - it just means scene duration won't be perfectly synced.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        out = subprocess.check_output(cmd, timeout=30).decode("utf-8").strip()
        return float(out)
    except Exception as exc:  # noqa: BLE001 - any ffprobe failure is non-fatal here
        log.warning("Could not read audio duration via ffprobe: %s", exc)
        return settings.default_scene_duration_seconds


def _add_silence_padding(input_path: str, output_path: str, pad_seconds: float) -> float:
    """Prepends `pad_seconds` of lead-in silence (fixes clipped first
    syllables) and normalizes the sample rate. Returns the final duration.

    If ffmpeg padding fails for any reason, the raw (unpadded) audio is
    kept instead of failing the whole narration step.
    """
    temp_out = f"{output_path}.padded.mp3"
    pad_ms = int(pad_seconds * 1000)

    cmd = [
        settings.ffmpeg_binary, "-y", "-i", input_path,
        "-af", f"adelay={pad_ms}|{pad_ms},aformat=sample_rates=44100",
        "-c:a", "libmp3lame", "-b:a", "192k",
        temp_out,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=60)
        os.replace(temp_out, output_path)
    except Exception as exc:  # noqa: BLE001
        log.error("Audio padding failed, keeping raw narration audio: %s", exc)
        if os.path.exists(temp_out):
            os.remove(temp_out)

    return _get_audio_duration_seconds(output_path)


class BaseVoiceProvider(ABC):
    """Interface for anything that can turn narration text into an audio file."""

    @abstractmethod
    async def generate_speech_async(
        self, text: str, output_path: str, voice: Optional[str] = None
    ) -> tuple[str, float]:
        """Generates speech and returns `(file_path, duration_seconds)`."""
        raise NotImplementedError


class EdgeTTSVoiceProvider(BaseVoiceProvider):
    """Free cloud TTS via Microsoft Edge TTS, with lead-in silence padding
    so narration doesn't clip its first syllable."""

    def __init__(self, default_voice: Optional[str] = None):
        self.default_voice = default_voice or settings.tts_voice

    async def generate_speech_async(
        self, text: str, output_path: str, voice: Optional[str] = None
    ) -> tuple[str, float]:
        import edge_tts

        selected_voice = voice or self.default_voice
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        log.info("Generating narration audio (voice=%s): %r", selected_voice, text[:60])
        communicate = edge_tts.Communicate(text, selected_voice)
        await communicate.save(output_path)

        duration = _add_silence_padding(output_path, output_path, settings.tts_lead_in_padding_seconds)
        return output_path, duration
