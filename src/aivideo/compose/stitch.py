"""Clip combination helpers: concat, audio overlay, fit-to-size.

Targets moviepy 2.x (renamed methods: set_* -> with_*, resize -> resized, etc.).
"""

from __future__ import annotations

from pathlib import Path

from moviepy import AudioFileClip, VideoClip, VideoFileClip, concatenate_videoclips


def load(path: str | Path) -> VideoFileClip:
    return VideoFileClip(str(path))


def concat(clips: list[VideoClip], method: str = "compose") -> VideoClip:
    """Join clips end-to-end. method='compose' tolerates differing sizes."""
    return concatenate_videoclips(clips, method=method)


def with_audio(clip: VideoClip, audio_path: str | Path) -> VideoClip:
    """Replace the clip's audio track with the given file (mp3/wav)."""
    audio = AudioFileClip(str(audio_path))
    return clip.with_audio(audio)


def fit_to_size(clip: VideoClip, width: int, height: int) -> VideoClip:
    """Resize+crop a clip to exactly width x height (cover behavior)."""
    target_ratio = width / height
    cw, ch = clip.size
    src_ratio = cw / ch
    if src_ratio > target_ratio:
        new_h = height
        new_w = int(round(new_h * src_ratio))
    else:
        new_w = width
        new_h = int(round(new_w / src_ratio))
    resized = clip.resized(new_size=(new_w, new_h))
    x = (new_w - width) // 2
    y = (new_h - height) // 2
    return resized.cropped(x1=x, y1=y, x2=x + width, y2=y + height)
