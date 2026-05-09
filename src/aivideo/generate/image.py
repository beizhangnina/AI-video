"""Image generation via Token360 (OpenAI-compatible /v1/images/generations)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from ..cache import cache_path, hit
from ..client import openai_client
from ..config import settings


def image(
    prompt: str,
    *,
    size: str = "1024x1792",
    model: str | None = None,
    quality: str = "standard",
    style: str = "vivid",
    use_cache: bool = True,
) -> Path:
    """Generate one image. Returns a local PNG path.

    Default size 1024x1792 matches the vertical 1080x1920 video target
    closely enough for a downstream resize/crop.
    """
    model = model or settings.image_model
    params = {
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "style": style,
    }
    path = cache_path("image", model, params, "png")
    if use_cache and hit(path):
        return path

    resp = openai_client().images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality=quality,
        style=style,
        n=1,
    )
    item = resp.data[0]
    if getattr(item, "b64_json", None):
        path.write_bytes(base64.b64decode(item.b64_json))
    elif getattr(item, "url", None):
        path.write_bytes(httpx.get(item.url, timeout=60).content)
    else:
        raise RuntimeError("Image response had neither b64_json nor url")
    return path
