"""Narrated-story pipeline: topic -> scenes -> images -> motion + TTS -> mp4.

Two motion modes:
- 'video_gen' (default): each scene runs first-frame I2V via Token360, giving
  real animated video clips. Higher cost / slower.
- 'kenburns': each scene is a still AI image with smooth zoom/pan. Cheap, fast.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from ..compose import kenburns, render, stitch, subtitles
from ..config import settings
from ..generate import image, llm, tts, video

_SYSTEM = """You are a creative video director. Given a topic and a target
duration, produce a JSON object with the schema:

{
  "title": str,
  "scenes": [
    {
      "narration": str,            # 1-2 short sentences, spoken aloud
      "image_prompt": str,         # vivid description for an AI image model
      "motion_prompt": str,        # how the scene should animate
      "seconds": int               # one of [3,4,5,6,7,8,9,10,12]
    }
  ]
}

Rules:
- Scenes must sum to roughly the target duration.
- 4-7 scenes total.
- Image prompts should be visually rich, single-frame, no text overlay.
- Motion prompts should be brief: subject + verb + camera hint.
- Narration should sound natural when read by TTS.
"""


def _build_outline(topic: str, style: str, duration_target: int, model: str | None) -> dict:
    user = (
        f"Topic: {topic}\n"
        f"Visual style: {style}\n"
        f"Target total duration: {duration_target} seconds.\n"
        f"Output JSON only."
    )
    return llm.script(user, system=_SYSTEM, model=model, json_mode=True)


def run(
    *,
    topic: str,
    style: str = "cinematic, vivid colors",
    voice: str | None = None,
    duration_target: int = 30,
    motion: Literal["video_gen", "kenburns"] = "video_gen",
    portrait: str | None = None,
    output: str | Path = "story.mp4",
    llm_model: str | None = None,
    image_model: str | None = None,
    video_model: str | None = None,
) -> Path:
    """Generate a narrated story video.

    portrait: optional asset:// URI of a Virtual Portrait or RealFace asset
              to keep a character consistent across scenes (Seedance 2.0 only).
    """
    print(f"[narrated_story] outlining: {topic!r} ({duration_target}s, motion={motion})")
    outline = _build_outline(topic, style, duration_target, llm_model)
    scenes = outline.get("scenes") or []
    if not scenes:
        raise RuntimeError(f"LLM produced no scenes: {json.dumps(outline)[:500]}")

    print(f"[narrated_story] {len(scenes)} scenes; generating media…")
    clips = []
    cues = []
    cursor = 0.0

    for i, sc in enumerate(scenes, 1):
        print(f"[scene {i}/{len(scenes)}] image -> motion={motion}")
        img = image.image(sc["image_prompt"], size="1024x1792", model=image_model)
        if motion == "video_gen":
            duration = int(sc.get("seconds", 5))
            mp4 = video.from_first_frame(
                img,
                sc.get("motion_prompt", "subtle camera push-in"),
                duration=duration,
                model=video_model,
                portrait=portrait,
            )
            clip = stitch.fit_to_size(stitch.load(mp4), settings.width, settings.height)
        else:
            duration = float(sc.get("seconds", 5))
            clip = kenburns.from_image(img, duration=duration)

        cues.append(
            subtitles.Cue(
                text=sc["narration"],
                start=cursor,
                end=cursor + clip.duration,
            )
        )
        cursor += clip.duration
        clips.append(clip)

    print("[narrated_story] generating narration audio…")
    full_narration = " ".join(s["narration"] for s in scenes)
    audio = tts.speak(full_narration, voice=voice)

    print("[narrated_story] composing final video…")
    base = stitch.concat(clips)
    base = stitch.with_audio(base, audio)
    final = subtitles.burn(base, cues)

    return render.to_mp4(final, output)
