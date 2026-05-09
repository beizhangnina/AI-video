"""Planner agent: turns a fuzzy idea into a strict Plan.

Uses an LLM with JSON mode and a strong system prompt that constrains the
output to the Plan schema.

Honors optional preset overrides (style / duration / aspect / mood / voice /
pacing). When the caller passes a preset, we both inject it into the system
prompt AND post-validate that the planner emitted matching fields, repairing
mismatches where unambiguous.
"""

from __future__ import annotations

from .. import presets as presets_mod
from ..generate import llm
from .schemas import Keyframe, Plan, Style

SYSTEM = """You are a creative video director planning a SHORT video.
Your job is to translate a fuzzy idea into a complete, executable Plan.

Output ONE JSON object matching this schema EXACTLY:

{
  "title": str,                          // short, catchy
  "logline": str,                        // one sentence summary
  "style": {
    "visual": str,                       // rich descriptor; honor any provided preset verbatim
    "voice": str,                        // TTS voice id: alloy | echo | fable | onyx | nova | shimmer
    "voice_direction": str,              // delivery, e.g. "warm narrator, unhurried"
    "aspect": "9:16" | "16:9" | "1:1",
    "duration_target": int               // total seconds
  },
  "narration": str,                      // full voiceover concatenated
  "keyframes": [
    {
      "id": "k01",                       // k01, k02, ... in order
      "narration": str,                  // 1-2 short sentences spoken during this beat
      "image_prompt": str,               // VIVID single-frame description, no text overlay
      "motion_prompt": str,              // brief: subject + verb + camera hint
      "seconds": int,                    // MUST be one of [3,4,5,6,7,8,9,10,12]
      "transition_in": "cut" | "fade",
      "role": "opening" | "build" | "climax" | "resolution",
      "continues_from_prev": bool        // if true, executor will use prev scene's last
                                         // frame as this scene's first frame instead of
                                         // generating a new image. Use sparingly:
                                         //  - to fake a single long shot >12s
                                         //  - to make a transition seamless
    }
  ]
}

Hard rules:
- 4 to 8 keyframes total.
- Sum(keyframes[*].seconds) ~= style.duration_target (within 20%).
- For sequences longer than 12 seconds in a single continuous shot, split
  into 2-3 chained keyframes with continues_from_prev=true on the followers.
- narration MUST equal the concatenation of keyframes[*].narration with single spaces.
- image_prompt: visually rich, painterly, NO embedded text or logos.
- motion_prompt: brief, e.g. "octopus drifts upward as camera pulls back, soft current".
- Match TTS voice to the tone (warm story -> alloy/nova; gritty -> onyx; bright -> shimmer).
- If the idea is in Chinese, write narration in Chinese; otherwise English.

Narrative structure (assign roles like a screenwriter):
- The first keyframe MUST have role="opening" (establishes setting/character).
- The last keyframe MUST have role="resolution" (lands the emotional beat).
- 0 or 1 keyframe in the middle MAY be role="climax" (the strongest visual / emotional peak).
- All other keyframes are role="build".
- Pace the narrative: open simple, build, peak, close. Avoid flat sequences.

Output JSON ONLY. No prose.
"""


def plan(
    idea: str,
    *,
    llm_model: str | None = None,
    temperature: float = 0.85,
    style: str | None = None,
    duration: str | int | None = None,
    aspect: str | None = None,
    mood: str | None = None,
    voice: str | None = None,
    pacing: str | None = None,
) -> Plan:
    """Convert an idea string into a validated Plan.

    style/duration/aspect/mood/voice/pacing accept either preset slugs (see
    aivideo.presets) or raw user descriptions. They become hard constraints
    on the LLM output.

    Raises ValueError if the LLM returns a structurally invalid plan.
    """
    style_str = presets_mod.resolve_style(style)
    duration_target = presets_mod.resolve_duration(duration)
    aspect_str = presets_mod.resolve_aspect(aspect)
    mood_str = presets_mod.resolve_mood(mood)
    voice_id = presets_mod.resolve_voice(voice)
    pacing_str = presets_mod.resolve_pacing(pacing)

    constraints = []
    if style_str:
        constraints.append(f"- Visual style (use this verbatim in style.visual): {style_str}")
    if duration_target:
        constraints.append(f"- Duration target: {duration_target} seconds")
    if aspect_str:
        constraints.append(f"- Aspect: {aspect_str}")
    if mood_str:
        constraints.append(f"- Mood / tone: {mood_str}")
    if voice_id:
        constraints.append(f"- TTS voice id (use exactly): {voice_id}")
    if pacing_str:
        constraints.append(f"- Pacing: {pacing_str}")

    constraint_block = (
        "Constraints (honor strictly):\n" + "\n".join(constraints) + "\n\n"
        if constraints
        else ""
    )

    raw = llm.script(
        prompt=f"Idea: {idea}\n\n{constraint_block}Produce the Plan JSON.",
        system=SYSTEM,
        model=llm_model,
        json_mode=True,
        temperature=temperature,
    )
    plan_obj = _validate(raw)

    # Post-hoc enforcement: if the LLM drifted from the preset, snap key
    # fields back to the user's choice.
    if style_str:
        plan_obj.style.visual = style_str
    if duration_target:
        plan_obj.style.duration_target = duration_target
    if aspect_str:
        plan_obj.style.aspect = aspect_str
    if voice_id:
        plan_obj.style.voice = voice_id

    return plan_obj


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
    allowed_roles = {"opening", "build", "climax", "resolution"}
    keyframes: list[Keyframe] = []
    for i, raw in enumerate(data["keyframes"], 1):
        if raw.get("seconds") not in allowed_durations:
            raise ValueError(
                f"Keyframe {raw.get('id', i)} has invalid seconds={raw.get('seconds')}; "
                f"must be one of {sorted(allowed_durations)}"
            )
        role = raw.get("role", "build")
        if role not in allowed_roles:
            role = "build"
        keyframes.append(Keyframe(
            id=raw.get("id") or f"k{i:02d}",
            narration=raw["narration"],
            image_prompt=raw["image_prompt"],
            motion_prompt=raw["motion_prompt"],
            seconds=int(raw["seconds"]),
            transition_in=raw.get("transition_in", "cut"),
            role=role,
            continues_from_prev=bool(raw.get("continues_from_prev", False)),
        ))

    # Repair narrative structure if the LLM forgot:
    if keyframes:
        keyframes[0].role = "opening"
        keyframes[-1].role = "resolution"
        # First keyframe can never continue from a non-existent predecessor.
        keyframes[0].continues_from_prev = False

    return Plan(
        title=data["title"],
        logline=data["logline"],
        style=style,
        narration=data["narration"],
        keyframes=keyframes,
    )
