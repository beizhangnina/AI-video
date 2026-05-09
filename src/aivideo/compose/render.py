"""Final mp4 encoding."""

from __future__ import annotations

from pathlib import Path

from moviepy.video.VideoClip import VideoClip

from ..config import OUTPUT_DIR, settings


def to_mp4(
    clip: VideoClip,
    output: str | Path,
    *,
    fps: int | None = None,
    codec: str = "libx264",
    audio_codec: str = "aac",
    bitrate: str = "5000k",
) -> Path:
    """Encode and write an mp4. Returns the absolute path written."""
    fps = fps or settings.fps
    out = Path(output)
    if not out.is_absolute():
        out = OUTPUT_DIR / out
    out.parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(
        str(out),
        fps=fps,
        codec=codec,
        audio_codec=audio_codec,
        bitrate=bitrate,
        threads=4,
        preset="medium",
        logger=None,
    )
    return out
