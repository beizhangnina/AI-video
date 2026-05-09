"""Ken Burns effect: slow zoom over a still image to fake motion.

Implementation: pre-resize the image to cover the output box, then for each
frame compute a centered crop window scaled by an animated zoom factor and
upscale back to (width x height). Pure numpy + Pillow + moviepy VideoClip,
which avoids moviepy's effect-pipeline API churn.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from moviepy import VideoClip
from PIL import Image

from ..config import settings


def from_image(
    image_path: str | Path,
    duration: float = 5.0,
    *,
    width: int | None = None,
    height: int | None = None,
    zoom_from: float = 1.0,
    zoom_to: float = 1.15,
) -> VideoClip:
    """Animate a still image with a smooth zoom from zoom_from to zoom_to.

    Output is exactly width x height (defaults to settings target).
    """
    width = width or settings.width
    height = height or settings.height

    pil = Image.open(str(image_path)).convert("RGB")
    iw, ih = pil.size
    target_ratio = width / height
    src_ratio = iw / ih
    if src_ratio > target_ratio:
        cover_h = height
        cover_w = int(round(cover_h * src_ratio))
    else:
        cover_w = width
        cover_h = int(round(cover_w / src_ratio))
    pil = pil.resize((cover_w, cover_h), Image.LANCZOS)
    base = np.array(pil)

    def make_frame(t: float) -> np.ndarray:
        progress = (t / duration) if duration else 0.0
        zoom = zoom_from + (zoom_to - zoom_from) * progress
        crop_w = max(1, min(cover_w, int(round(width / zoom))))
        crop_h = max(1, min(cover_h, int(round(height / zoom))))
        x = (cover_w - crop_w) // 2
        y = (cover_h - crop_h) // 2
        cropped = base[y:y + crop_h, x:x + crop_w]
        return np.array(
            Image.fromarray(cropped).resize((width, height), Image.LANCZOS)
        )

    return VideoClip(make_frame, duration=duration)
