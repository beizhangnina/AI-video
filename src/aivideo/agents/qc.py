"""Quality control agent.

Sends a generated artifact (image or video frame) plus the original intent
to a multimodal LLM and asks for a score + critique. If the score is below
threshold, the executor will request a refined prompt and retry once.

Token360 is OpenAI-compatible, so vision works through chat.completions
with image_url content parts.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from ..client import openai_client
from ..config import settings
from .schemas import Keyframe, QCReport

_THRESHOLD = 0.65

_SYSTEM = """You are a strict but fair video QC reviewer.
Given the director's intent (image_prompt + motion_prompt + style) and the
generated artifact, score the artifact 0.0 to 1.0 and write a brief critique.

Reply with ONE JSON object EXACTLY:
{
  "score": float,           // 0.0 to 1.0
  "critique": str,          // 1-2 sentences: what works, what doesn't
  "needs_retry": bool,      // true if score < 0.65 OR critical flaw
  "refinement": str         // if needs_retry: a concrete suggestion to improve the prompt; else ""
}

Score guide:
- 0.85+ : matches intent and style well
- 0.65-0.85: usable but minor issues
- below 0.65: major mismatch, retry recommended

Output JSON only.
"""


def _b64(path: Path, mime: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def review_image(
    keyframe: Keyframe,
    image_path: str | Path,
    style_visual: str,
    *,
    model: str | None = None,
) -> QCReport:
    path = Path(image_path)
    intent = (
        f"Style: {style_visual}\n"
        f"Image prompt: {keyframe.image_prompt}\n"
        f"Will be animated as: {keyframe.motion_prompt}"
    )
    body = _ask(intent, _b64(path, "image/png"), model=model)
    return QCReport(
        keyframe_id=keyframe.id,
        artifact_kind="image",
        artifact_path=str(path),
        score=float(body["score"]),
        passed=float(body["score"]) >= _THRESHOLD and not body.get("needs_retry", False),
        critique=body["critique"],
        refined_prompt=body.get("refinement") or None,
    )


def review_video(
    keyframe: Keyframe,
    video_path: str | Path,
    style_visual: str,
    *,
    model: str | None = None,
) -> QCReport:
    """Review by sampling a mid-frame from the generated video.

    Cheap-but-effective: vision LLMs accept stills; we extract frame 50%
    through the clip, encode it, and score against the motion intent.
    """
    path = Path(video_path)
    frame_b64 = _extract_mid_frame_b64(path)
    intent = (
        f"Style: {style_visual}\n"
        f"Image prompt: {keyframe.image_prompt}\n"
        f"Motion prompt: {keyframe.motion_prompt}\n"
        f"This is a still sampled from the generated video clip."
    )
    body = _ask(intent, frame_b64, model=model)
    return QCReport(
        keyframe_id=keyframe.id,
        artifact_kind="video",
        artifact_path=str(path),
        score=float(body["score"]),
        passed=float(body["score"]) >= _THRESHOLD and not body.get("needs_retry", False),
        critique=body["critique"],
        refined_prompt=body.get("refinement") or None,
    )


def _ask(intent: str, image_data_url: str, *, model: str | None) -> dict:
    model = model or settings.llm_model
    resp = openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Director's intent:\n{intent}"},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content or "{}")


def _extract_mid_frame_b64(video_path: Path) -> str:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from PIL import Image
    import io

    with VideoFileClip(str(video_path)) as clip:
        frame = clip.get_frame(clip.duration / 2)
    img = Image.fromarray(frame)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
