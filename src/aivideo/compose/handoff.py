"""Frame-handoff utilities.

Used to tie consecutive video clips together: take the final frame of clip N
and feed it as the first frame of clip N+1's video generation request. This
yields a seamless visual transition instead of a hard cut, which is essential
for either (a) faking a single long shot from multiple <=12s API calls, or
(b) smoothing scene-to-scene cuts.
"""

from __future__ import annotations

from pathlib import Path

from moviepy import VideoFileClip
from PIL import Image


def last_frame(video_path: str | Path, out_path: str | Path | None = None) -> Path:
    """Extract the final frame of a video as a PNG. Returns the PNG path.

    If out_path is omitted, writes alongside the video as <stem>-last.png.
    """
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-last.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    with VideoFileClip(str(src)) as clip:
        # Sample 1/30s before the end to dodge any encoder-padded blank frame.
        t = max(0.0, clip.duration - 1.0 / 30.0)
        frame = clip.get_frame(t)
    Image.fromarray(frame).save(out, format="PNG")
    return out


def first_frame(video_path: str | Path, out_path: str | Path | None = None) -> Path:
    """Symmetric helper for the opening frame (rarely needed, but cheap to have)."""
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-first.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    with VideoFileClip(str(src)) as clip:
        frame = clip.get_frame(0.0)
    Image.fromarray(frame).save(out, format="PNG")
    return out
