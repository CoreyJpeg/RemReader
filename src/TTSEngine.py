from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline


class TTSEngine:

    SAMPLE_RATE = 24000

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.0
    ):

        self.voice = voice
        self.speed = speed

        # Get language from voice name
        self.language = self.get_language_from_voice(
            voice
        )

        # Select best available device
        if torch.cuda.is_available():
            self.device = "cuda"

        elif (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            self.device = "mps"

        else:
            self.device = "cpu"

        print(
            f"TTS device: {self.device}"
        )

        print(
            f"TTS language: {self.language}"
        )

        # Build initial Kokoro pipeline
        self.pipeline = self.create_pipeline(
            self.language
        )


    def get_language_from_voice(
        self,
        voice: str
    ) -> str:
        """
        Kokoro voice names use their first letter
        to represent the language.
        """

        return voice[0]


    def create_pipeline(
        self,
        language: str
    ):
        """
        Create a Kokoro pipeline for a language.
        """

        return KPipeline(
            lang_code=language,
            repo_id="hexgrad/Kokoro-82M",
            device=self.device
        )


    def set_voice(
        self,
        voice: str
    ):
        """
        Change voice.

        Rebuild the language pipeline only if
        the new voice uses a different language.
        """

        new_language = self.get_language_from_voice(
            voice
        )

        # Different language requires a new pipeline
        if new_language != self.language:

            print(
                f"Changing TTS language "
                f"{self.language} -> {new_language}"
            )

            self.language = new_language

            self.pipeline = self.create_pipeline(
                self.language
            )

        # Same language can reuse existing pipeline
        self.voice = voice


    def generate_audio(
        self,
        text: str
    ) -> np.ndarray:

        generator = self.pipeline(
            text,
            voice=self.voice,
            speed=self.speed
        )

        audio_parts = []

        for _, _, audio in generator:

            if audio is None:
                continue

            if hasattr(
                audio,
                "cpu"
            ):
                audio = (
                    audio
                    .cpu()
                    .numpy()
                )

            else:
                audio = np.asarray(
                    audio
                )

            audio_parts.append(
                audio
            )

        if not audio_parts:
            raise RuntimeError(
                "Kokoro produced no audio."
            )

        return np.concatenate(
            audio_parts
        )


    def save_audio(
        self,
        audio: np.ndarray,
        output_path: str | Path
    ):

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        sf.write(
            output_path,
            audio,
            self.SAMPLE_RATE
        )