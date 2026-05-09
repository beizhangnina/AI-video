"""AI generators — each returns a local file path or parsed JSON."""

from . import image, llm, tts, video

__all__ = ["llm", "image", "tts", "video"]
