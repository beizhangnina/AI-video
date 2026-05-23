"""Auto pipeline: idea -> Plan -> execute (with QC) -> compose -> deliver.

This is the entry point of the \"video app\". A single function call takes a
fuzzy idea string and returns a RunResult pointing at runs/<id>/final.mp4
plus a human-readable runs/<id>/report.md.
"""

from __future__ import annotations

from pathlib import Path

from .. import assets as assets_mod
from .. import runs as run_paths
from ..agents import executor, planner
from ..agents.schemas import Plan, RunResult
from ..compose import kenburns, render, stitch, subtitles
from ..config import settings
from ..generate import tts


def _resolve_portrait(portrait: str | None) -> str | None:
    """Accept either an asset:// URI or a local image path.

    If a local path is provided, upload it to a Virtual Portrait group (no
    real-person verification needed) and return the resulting asset:// URI.
    Returns None if portrait is None.
    """
    if not portrait:
        return None
    if portrait.startswith("asset://"):
        return portrait
    p = Path(portrait)
    if p.exists() and p.is_file():
        print(f"[auto] uploading portrait {p.name} to Virtual Portrait group…")
        uris = assets_mod.setup_virtual_portrait(f"aivideo-portrait-{p.stem}", [p])
        return uris[0]
    return portrait


def _aspect_to_size(aspect: str) -> tuple[int, int]:
    if aspect == "9:16":
        return 1080, 1920
    if aspect == "16:9":
        return 1920, 1080
    if aspect == "1:1":
        return 1080, 1080
    return settings.width, settings.height


def make(
    idea: str,
    *,
    style: str | None = None,
    duration: str | int | None = None,
    aspect: str | None = None,
    mood: str | None = None,
    voice: str | None = None,
    pacing: str | None = None,
    motion: str = "video_gen",
    qc_enabled: bool = True,
    portrait: str | None = None,
    llm_model: str | None = None,
    no_narration: bool = False,
) -> RunResult:
    """Idea string -> finished mp4 + run folder. Returns a RunResult.

    Presets (any of these accept either a slug from aivideo.presets OR a raw
    user-supplied descriptor):
      style: cyberpunk | ghibli | pixar_3d | photorealistic | wuxia | cinematic |
             anime | cartoon_2d | noir | watercolor
      duration: snippet (15s) | short (30s) | standard (45s) | long_form (75s) |
                a raw integer
      aspect: vertical (9:16) | horizontal (16:9) | square (1:1)
      mood: cheerful | melancholic | mysterious | epic | comedic | romantic |
            suspenseful | serene
      voice: warm | energetic | deep | bright | gentle | dramatic
      pacing: slow | normal | fast
    """
    run_dir = run_paths.new_run(idea)
    rid = run_paths.run_id(run_dir)
    print(f"[auto] run_id={rid}  ({run_dir})")

    print("[auto] planning…")
    plan_obj: Plan = planner.plan(
        idea,
        llm_model=llm_model,
        style=style,
        duration=duration,
        aspect=aspect,
        mood=mood,
        voice=voice,
        pacing=pacing,
    )
    plan_obj.write(run_paths.plan_path(run_dir))
    print(f"[auto] plan: {plan_obj.title} | {len(plan_obj.keyframes)} keyframes "
          f"| {plan_obj.style.duration_target}s | aspect={plan_obj.style.aspect}")

    width, height = _aspect_to_size(plan_obj.style.aspect)
    resolved_portrait = _resolve_portrait(portrait)

    reports, flagged = executor.execute(
        plan_obj,
        run_dir,
        motion=motion,
        portrait=resolved_portrait,
        qc_enabled=qc_enabled,
        generate_audio=no_narration,
    )

    if not no_narration:
        print("[auto] generating narration audio…")
        audio = tts.speak(plan_obj.narration, voice=plan_obj.style.voice)
        narration_target = run_paths.narration_path(run_dir)
        narration_target.write_bytes(audio.read_bytes())

    print("[auto] composing final video…")
    clips = []
    cues = []
    cursor = 0.0
    for kf in plan_obj.keyframes:
        if motion == "video_gen":
            mp4 = run_paths.scene_video(run_dir, kf.id)
            clip = stitch.fit_to_size(stitch.load(mp4), width, height)
        else:
            png = run_paths.scene_image(run_dir, kf.id)
            clip = kenburns.from_image(png, duration=float(kf.seconds), width=width, height=height)
        cues.append(subtitles.Cue(text=kf.narration, start=cursor, end=cursor + clip.duration))
        cursor += clip.duration
        clips.append(clip)

    if no_narration:
        # Keep the per-clip ambient audio Seedance baked in; no subtitles.
        final = stitch.concat(clips)
    else:
        base = stitch.with_audio(stitch.concat(clips), narration_target)
        final = subtitles.burn(base, cues)
    final_path = run_paths.final_path(run_dir)
    render.to_mp4(final, final_path)

    _write_report(run_dir, plan_obj, reports, flagged)
    print(f"[auto] done -> {final_path}")
    print(f"[auto] report -> {run_paths.report_path(run_dir)}")

    return RunResult(
        run_id=rid,
        run_dir=str(run_dir),
        plan_path=str(run_paths.plan_path(run_dir)),
        final_video=str(final_path),
        qc_reports=reports,
        flagged_keyframes=flagged,
    )


def _write_report(run_dir: Path, plan_obj: Plan, reports, flagged) -> None:
    lines = [
        f"# {plan_obj.title}",
        "",
        f"**Logline.** {plan_obj.logline}",
        "",
        f"**Style.** {plan_obj.style.visual}  ",
        f"**Voice.** {plan_obj.style.voice} — {plan_obj.style.voice_direction}  ",
        f"**Aspect / target.** {plan_obj.style.aspect}, ~{plan_obj.style.duration_target}s",
        "",
        "## Keyframes",
        "",
    ]
    for kf in plan_obj.keyframes:
        lines += [
            f"### {kf.id} — {kf.seconds}s",
            f"- **Narration.** {kf.narration}",
            f"- **Image prompt.** {kf.image_prompt}",
            f"- **Motion prompt.** {kf.motion_prompt}",
            "",
        ]

    lines += ["## QC reports", ""]
    for r in reports:
        flag = "FLAGGED" if not r.passed else "ok"
        lines.append(
            f"- **{r.keyframe_id}** ({r.artifact_kind}, {flag}, score={r.score:.2f}): {r.critique}"
        )

    if flagged:
        lines += ["", f"**Flagged keyframes (review manually):** {', '.join(flagged)}"]
    else:
        lines += ["", "All keyframes passed QC."]

    run_paths.report_path(run_dir).write_text("\n".join(lines), encoding="utf-8")
