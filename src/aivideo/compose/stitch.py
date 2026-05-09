"""Clip combination helpers: concat, audio overlay, crossfade."""

from __future__ import annotations

from pathlib import Path

from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import VideoClip


def load(path: str | Path) -> VideoFileClip:
    return VideoFileClip(str(path))


def concat(clips: list[VideoClip], method: str = "compose") -> VideoClip:
    """Join clips end-to-end. method='compose' tolerates differing sizes."""
    return concatenate_videoclips(clips, method=method)


def with_audio(clip: VideoClip, audio_path: str | Path) -> VideoClip:
    """Replace the clip's audio track with the given file (mp3/wav)."""
    audio = AudioFileClip(str(audio_path))
    return clip.set_audio(audio)


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
    resized = clip.resize(newsize=(new_w, new_h))
    x = (new_w - width) // 2
    y = (new_h - height) // 2
    return resized.crop(x1=x, y1=y, x2=x + width, y2=y + height)
