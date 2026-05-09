"""Planner agent: turns a fuzzy idea into a strict Plan.

Uses an LLM with JSON mode and a strong system prompt that constrains the
output to the Plan schema. Two-pass design optional (logline first, then
keyframes) but kept as a single pass for simplicity unless the plan is bad.
"""

from __future__ import annotations

from ..generate import llm
from .schemas import Keyframe, Plan, Style

SYSTEM = """You are a creative video director planning a SHORT vertical video.
Your job is to translate a fuzzy idea into a complete, executable Plan.

Output ONE JSON object matching this schema EXACTLY:

{
  "title": str,                          // short, catchy
  "logline": str,                        // one sentence summary
  "style": {
    "visual": str,                       // e.g. "watercolor storybook, warm tones, soft focus"
    "voice": str,                        // TTS voice: alloy | echo | fable | onyx | nova | shimmer
    "voice_direction": str,              // delivery, e.g. "warm narrator, unhurried"
    "aspect": "9:16" | "16:9" | "1:1",
    "duration_target": int               // total seconds, default 30
  },
  "narration": str,                      // full voiceover text concatenated
  "keyframes": [
    {
      "id": "k01",                       // k01, k02, ... in order
      "narration": str,                  // 1-2 short sentences spoken during this beat
      "image_prompt": str,               // VIVID single-frame description, no text overlay
      "motion_prompt": str,              // brief: subject + verb + camera hint
      "seconds": int,                    // MUST be one of [3,4,5,6,7,8,9,10,12]
      "transition_in": "cut" | "fade"
    }
  ]
}

Hard rules:
- 4 to 7 keyframes total.
- Sum(keyframes[*].seconds) ~= style.duration_target (within 20%).
- narration MUST equal the concatenation of keyframes[*].narration with single spaces.
- image_prompt: visually rich, painterly, NO embedded text or logos.
- motion_prompt: brief, e.g. "octopus drifts upward as camera pulls back, soft current".
- Match TTS voice to the tone (warm story -> alloy/nova; gritty -> onyx; bright -> shimmer).
- If the idea is in Chinese, write narration in Chinese; otherwise English.
- Output JSON ONLY. No prose.
"""


def plan(idea: str, *, llm_model: str | None = None, temperature: float = 0.85) -> Plan:
    """Convert an idea string into a validated Plan.

    Raises ValueError if the LLM returns a structurally invalid plan.
    """
    raw = llm.script(
        prompt=f"Idea: {idea}\n\nProduce the Plan JSON.",
        system=SYSTEM,
        model=llm_model,
        json_mode=True,
        temperature=temperature,
    )
    return _validate(raw)


def replan_keyframe(
    plan_obj: Plan,
    keyframe_id: str,
    critique: str,
    *,
    llm_model: str | None = None,
) -> str:
    """Ask the LLM for a refined image_prompt given a QC critique.

    Returns the new image_prompt to use on retry.
    """
    kf = next((k for k in plan_obj.keyframes if k.id == keyframe_id), None)
    if kf is None:
        raise ValueError(f"Keyframe {keyframe_id} not in plan")
    refined = llm.script(
        prompt=(
            f"Original image prompt: {kf.image_prompt}\n"
            f"Style: {plan_obj.style.visual}\n"
            f"Critique of the generated image: {critique}\n\n"
            "Write a single revised image prompt that addresses the critique. "
            "Output the revised prompt ONLY, no preamble."
        ),
        model=llm_model,
        temperature=0.6,
    )
    return refined.strip().strip('"')


def _validate(data: dict) -> Plan:
    required_top = {"title", "logline", "style", "narration", "keyframes"}
    if missing := required_top - data.keys():
        raise ValueError(f"Plan missing keys: {missing}")
    if not isinstance(data["keyframes"], list) or not data["keyframes"]:
        raise ValueError("Plan keyframes must be a non-empty list")

    style = Style(**{k: data["style"][k] for k in Style.__dataclass_fields__ if k in data["style"]})
    if style.aspect not in {"9:16", "16:9", "1:1"}:
        raise ValueError(f"Invalid aspect: {style.aspect}")

    allowed_durations = {3, 4, 5, 6, 7, 8, 9, 10, 12}
    keyframes = []
    for i, raw in enumerate(data["keyframes"], 1):
        if raw.get("seconds") not in allowed_durations:
            raise ValueError(
                f"Keyframe {raw.get('id', i)} has invalid seconds={raw.get('seconds')}; "
                f"must be one of {sorted(allowed_durations)}"
            )
        keyframes.append(Keyframe(
            id=raw.get("id") or f"k{i:02d}",
            narration=raw["narration"],
            image_prompt=raw["image_prompt"],
            motion_prompt=raw["motion_prompt"],
            seconds=int(raw["seconds"]),
            transition_in=raw.get("transition_in", "cut"),
        ))

    return Plan(
        title=data["title"],
        logline=data["logline"],
        style=style,
        narration=data["narration"],
        keyframes=keyframes,
    )
