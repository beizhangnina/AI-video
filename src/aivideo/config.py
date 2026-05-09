"""Centralized config — loads .env and exposes settings as a singleton."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "cache"
OUTPUT_DIR = REPO_ROOT / "output"
ASSETS_DIR = REPO_ROOT / "assets"

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    llm_model: str
    image_model: str
    tts_model: str
    tts_voice: str
    video_model: str
    width: int
    height: int
    fps: int


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required env var {name}. Copy .env.example to .env and fill it in."
        )
    return value


settings = Settings(
    api_key=_required("TOKEN360_API_KEY"),
    base_url=os.getenv("TOKEN360_BASE_URL", "https://api.token360.ai/v1"),
    llm_model=os.getenv("AIVIDEO_LLM_MODEL", "gpt-4o"),
    image_model=os.getenv("AIVIDEO_IMAGE_MODEL", "dall-e-3"),
    tts_model=os.getenv("AIVIDEO_TTS_MODEL", "tts-1-hd"),
    tts_voice=os.getenv("AIVIDEO_TTS_VOICE", "alloy"),
    video_model=os.getenv("AIVIDEO_VIDEO_MODEL", "seedance-2.0-fast"),
    width=int(os.getenv("AIVIDEO_WIDTH", "1080")),
    height=int(os.getenv("AIVIDEO_HEIGHT", "1920")),
    fps=int(os.getenv("AIVIDEO_FPS", "30")),
)
