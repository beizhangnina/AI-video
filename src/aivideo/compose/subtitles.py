"""Burn subtitles onto a video clip.

Renders text via Pillow (avoids ImageMagick dependency that moviepy.TextClip needs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from moviepy.video.VideoClip import ImageClip, VideoClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Cue:
    text: str
    start: float
    end: float


def _find_font(font_path: str | Path | None, size: int) -> ImageFont.FreeTypeFont:
    if font_path and Path(font_path).exists():
        return ImageFont.truetype(str(font_path), size)
    for candidate in [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _render_text(
    text: str,
    *,
    width: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke: tuple[int, int, int, int] = (0, 0, 0, 200),
    padding: int = 20,
) -> Image.Image:
    dummy = Image.new("RGBA", (width, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=8)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    img = Image.new("RGBA", (max(width, tw + padding * 2), th + padding * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = (img.size[0] - tw) // 2 - bbox[0]
    y = padding - bbox[1]
    d.multiline_text(
        (x, y),
        text,
        font=font,
        fill=color,
        align="center",
        spacing=8,
        stroke_width=3,
        stroke_fill=stroke,
    )
    return img


def burn(
    base: VideoClip,
    cues: list[Cue],
    *,
    font_path: str | Path | None = None,
    font_size: int = 48,
    bottom_margin_ratio: float = 0.12,
) -> VideoClip:
    """Overlay timed text cues on top of the base clip."""
    width, height = base.size
    font = _find_font(font_path, font_size)

    overlays: list[VideoClip] = [base]
    for cue in cues:
        img = _render_text(cue.text, width=width - 80, font=font)
        clip = (
            ImageClip(np.array(img))
            .set_start(cue.start)
            .set_end(cue.end)
            .set_position(("center", height - img.size[1] - int(height * bottom_margin_ratio)))
        )
        overlays.append(clip)
    return CompositeVideoClip(overlays, size=base.size)
