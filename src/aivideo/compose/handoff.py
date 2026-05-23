"""Frame-handoff utilities.

Used to tie consecutive video clips together: take the final frame of clip N
and feed it as the first frame of clip N+1's video generation request. This
yields a seamless visual transition instead of a hard cut, which is essential
for either (a) faking a single long shot from multiple <=12s API calls, or
(b) smoothing scene-to-scene cuts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *args],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (code {r.returncode}): {r.stderr.strip()}")


def last_frame(video_path: str | Path, out_path: str | Path | None = None) -> Path:
    """Extract the final frame of a video as a PNG. Returns the PNG path.

    Uses ffmpeg `-sseof` to seek from the end. moviepy was unreliable here:
    Seedance mp4s sometimes have a zero-byte padded final frame, and moviepy
    silently falls back to an early frame instead of the real last one,
    defeating the handoff chain entirely.
    """
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-last.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-sseof", "-0.1", "-i", str(src), "-update", "1", "-frames:v", "1", str(out))
    return out


def first_frame(video_path: str | Path, out_path: str | Path | None = None) -> Path:
    """Symmetric helper for the opening frame (rarely needed, but cheap to have)."""
    src = Path(video_path)
    out = Path(out_path) if out_path else src.with_name(f"{src.stem}-first.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-i", str(src), "-update", "1", "-frames:v", "1", str(out))
    return out
