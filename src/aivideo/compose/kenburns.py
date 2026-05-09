"""Ken Burns effect: slow zoom/pan over a still image to fake motion.

Used as the fallback when video generation is disabled (motion="kenburns").
"""

from __future__ import annotations

from pathlib import Path

from moviepy.video.VideoClip import ImageClip, VideoClip

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

    base = ImageClip(str(image_path)).set_duration(duration)
    bw, bh = base.size
    target_ratio = width / height
    src_ratio = bw / bh
    if src_ratio > target_ratio:
        new_h = height
        new_w = int(round(new_h * src_ratio))
    else:
        new_w = width
        new_h = int(round(new_w / src_ratio))
    base = base.resize(newsize=(new_w, new_h))

    def zoom(t: float) -> float:
        progress = t / duration if duration else 0
        return zoom_from + (zoom_to - zoom_from) * progress

    zoomed = base.resize(lambda t: zoom(t))

    def crop_center(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        x = max(0, (w - width) // 2)
        y = max(0, (h - height) // 2)
        return frame[y:y + height, x:x + width]

    return zoomed.fl(crop_center, apply_to=["mask"]).set_duration(duration)
