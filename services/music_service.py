import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseMusicProvider(ABC):
    @abstractmethod
    def generate_music(self, prompt: str, duration_sec: float, output_path: str) -> str:
        pass


class HuggingFaceMusicGenProvider(BaseMusicProvider):
    """Generates background music using Hugging Face Transformers MusicGen model."""

    def __init__(self, model_name: str = "facebook/musicgen-small"):
        self.model_name = model_name
        self.synthesizer = None

    def _lazy_init(self):
        if self.synthesizer is None:
            from transformers import pipeline
            logger.info(f"Loading MusicGen pipeline model: {self.model_name}")
            self.synthesizer = pipeline("text-to-audio", model=self.model_name)

    def generate_music(self, prompt: str, duration_sec: float, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logger.info(f"Generating MusicGen track ({duration_sec}s) for prompt: '{prompt}'")
        
        try:
            self._lazy_init()
            # ASSERT FOR PYLANCE: Confirms self.synthesizer is initialized and not None
            assert self.synthesizer is not None, "MusicGen synthesizer failed to initialize"

            # Calculate max length in tokens (~50 tokens per second of audio)
            max_tokens = int(duration_sec * 50)
            music = self.synthesizer(prompt, forward_params={"max_new_tokens": max_tokens})
            
            import scipy.io.wavfile as wav
            import numpy as np

            audio_data = music["audio"][0].T
            sample_rate = music["sampling_rate"]

            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data)

            wav.write(output_path, rate=sample_rate, data=audio_data)
            return output_path

        except Exception as e:
            logger.error(f"MusicGen generation failed: {e}. Skipping music track.")
            return ""