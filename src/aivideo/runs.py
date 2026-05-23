"""Per-run artifact folder management.

Every `aivideo make` invocation produces one folder under runs/<id>/ containing
the plan, every intermediate artifact, every QC report, and the final mp4.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .config import REPO_ROOT

RUNS_DIR = REPO_ROOT / "output"
RUNS_DIR.mkdir(exist_ok=True)


def _slugify(text: str, max_len: int = 32) -> str:
    text = re.sub(r"[^\w一-鿿-]+", "-", text.strip().lower())
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "run"


def new_run(idea: str) -> Path:
    """Allocate a fresh runs/<timestamp>-<slug>/ folder. Returns its path."""
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = RUNS_DIR / f"{ts}-{_slugify(idea)}"
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "scenes").mkdir()
    return folder


def run_id(folder: Path) -> str:
    return folder.name


def plan_path(folder: Path) -> Path:
    return folder / "plan.json"


def narration_path(folder: Path) -> Path:
    return folder / "narration.mp3"


def report_path(folder: Path) -> Path:
    return folder / "report.md"


def final_path(folder: Path) -> Path:
    return folder / "final.mp4"


def scene_image(folder: Path, kf_id: str) -> Path:
    return folder / "scenes" / f"{kf_id}-image.png"


def scene_video(folder: Path, kf_id: str) -> Path:
    return folder / "scenes" / f"{kf_id}-video.mp4"


def scene_qc(folder: Path, kf_id: str, kind: str) -> Path:
    return folder / "scenes" / f"{kf_id}-qc-{kind}.json"
