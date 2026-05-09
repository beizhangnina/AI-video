"""Text-to-speech via Token360 (OpenAI-compatible /v1/audio/speech)."""

from __future__ import annotations

from pathlib import Path

from ..cache import cache_path, hit
from ..client import openai_client
from ..config import settings


def speak(
    text: str,
    *,
    voice: str | None = None,
    model: str | None = None,
    speed: float = 1.0,
    use_cache: bool = True,
) -> Path:
    """Synthesize narration. Returns a local MP3 path."""
    model = model or settings.tts_model
    voice = voice or settings.tts_voice
    params = {"text": text, "voice": voice, "speed": speed}
    path = cache_path("tts", model, params, "mp3")
    if use_cache and hit(path):
        return path

    resp = openai_client().audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        speed=speed,
    )
    resp.write_to_file(str(path))
    return path
