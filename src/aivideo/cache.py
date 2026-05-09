"""Content-addressed disk cache for AI outputs.

Pattern: hash (kind, model, params) -> cache/<kind>/<hash>.<ext>
Reuse across runs avoids re-paying for identical LLM/image/TTS/video calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import CACHE_DIR


def _hash(kind: str, model: str, params: dict[str, Any]) -> str:
    payload = json.dumps(
        {"kind": kind, "model": model, "params": params},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def cache_path(kind: str, model: str, params: dict[str, Any], ext: str) -> Path:
    """Return the deterministic cache file path for a request.

    kind: "llm" | "image" | "tts" | "video"
    ext:  "json" | "png" | "mp3" | "mp4"
    """
    folder = CACHE_DIR / kind
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{_hash(kind, model, params)}.{ext}"


def hit(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0
