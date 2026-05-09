"""Executor agent: walks a Plan, generates each keyframe, runs QC, retries.

For each keyframe:
  1. image gen -> save scenes/<id>-image.png
  2. QC the image; if fail, ask planner for a refined prompt and retry once
  3. video gen (first-frame I2V) -> save scenes/<id>-video.mp4
  4. QC the video (sampled mid-frame); flag if still failing after retry

Returns the list of QCReports and the list of flagged keyframe ids.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .. import runs as run_paths
from ..generate import image as image_gen
from ..generate import video as video_gen
from . import planner, qc
from .schemas import Plan, QCReport


def execute(
    plan: Plan,
    run_dir: Path,
    *,
    motion: str = "video_gen",
    portrait: str | None = None,
    qc_enabled: bool = True,
    image_size: str = "1024x1792",
) -> tuple[list[QCReport], list[str]]:
    """Generate every keyframe's image and video into run_dir/scenes/.

    motion: "video_gen" (Token360 video gen) or "kenburns" (still + zoom only).
            kenburns mode skips video.from_first_frame and skips video QC.
    """
    reports: list[QCReport] = []
    flagged: list[str] = []

    for kf in plan.keyframes:
        print(f"[executor] {kf.id}: image gen…")
        img_cache_path = image_gen.image(kf.image_prompt, size=image_size)
        img_target = run_paths.scene_image(run_dir, kf.id)
        shutil.copyfile(img_cache_path, img_target)

        if qc_enabled:
            report = qc.review_image(kf, img_target, plan.style.visual)
            _persist_report(run_dir, kf.id, "image", report)
            reports.append(report)
            print(f"[qc] {kf.id} image: score={report.score:.2f} pass={report.passed}")

            if not report.passed:
                refined = report.refined_prompt or planner.replan_keyframe(plan, kf.id, report.critique)
                print(f"[executor] {kf.id}: image retry with refined prompt")
                img_cache_path = image_gen.image(refined, size=image_size)
                shutil.copyfile(img_cache_path, img_target)
                report2 = qc.review_image(kf, img_target, plan.style.visual)
                _persist_report(run_dir, kf.id, "image-retry", report2)
                reports.append(report2)
                print(f"[qc] {kf.id} image retry: score={report2.score:.2f} pass={report2.passed}")
                if not report2.passed:
                    flagged.append(kf.id)

        if motion == "kenburns":
            continue

        print(f"[executor] {kf.id}: video gen ({kf.seconds}s)…")
        vid_cache_path = video_gen.from_first_frame(
            img_target,
            kf.motion_prompt,
            duration=kf.seconds,
            portrait=portrait,
        )
        vid_target = run_paths.scene_video(run_dir, kf.id)
        shutil.copyfile(vid_cache_path, vid_target)

        if qc_enabled:
            vreport = qc.review_video(kf, vid_target, plan.style.visual)
            _persist_report(run_dir, kf.id, "video", vreport)
            reports.append(vreport)
            print(f"[qc] {kf.id} video: score={vreport.score:.2f} pass={vreport.passed}")
            if not vreport.passed and kf.id not in flagged:
                flagged.append(kf.id)

    return reports, flagged


def _persist_report(run_dir: Path, kf_id: str, kind: str, report: QCReport) -> None:
    path = run_paths.scene_qc(run_dir, kf_id, kind)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
