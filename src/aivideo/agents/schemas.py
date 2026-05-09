"""Strongly-typed contracts between the agents.

Plan is the artifact the planner produces and the executor consumes.
QCReport is what qc.review() returns for each artifact.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Style:
    visual: str                      # e.g. "watercolor storybook, warm tones"
    voice: str                       # TTS voice id, e.g. "alloy"
    voice_direction: str             # narration delivery, e.g. "warm, slow"
    aspect: str = "9:16"             # 9:16 vertical | 16:9 horizontal | 1:1 square
    duration_target: int = 30        # seconds


@dataclass
class Keyframe:
    id: str                          # k01, k02, ...
    narration: str                   # spoken during this beat
    image_prompt: str                # detailed visual for image gen
    motion_prompt: str               # how it should animate (subject + verb + camera)
    seconds: int                     # one of [3,4,5,6,7,8,9,10,12]
    transition_in: str = "cut"       # "cut" | "fade"
    role: str = "build"              # "opening" | "build" | "climax" | "resolution"
    continues_from_prev: bool = False  # True: skip image gen, use prev scene's last frame
                                       # for seamless transition / chained long shots


@dataclass
class Plan:
    title: str
    logline: str                     # one-sentence summary
    style: Style
    narration: str                   # full voiceover text (concatenation of keyframe narrations)
    keyframes: list[Keyframe]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        style = Style(**data["style"])
        keyframes = [Keyframe(**kf) for kf in data["keyframes"]]
        return cls(
            title=data["title"],
            logline=data["logline"],
            style=style,
            narration=data["narration"],
            keyframes=keyframes,
        )

    @classmethod
    def read(cls, path: str | Path) -> Plan:
        return cls.from_dict(json.loads(Path(path).read_text()))


@dataclass
class QCReport:
    keyframe_id: str
    artifact_kind: str               # "image" | "video"
    artifact_path: str
    score: float                     # 0.0 - 1.0
    passed: bool                     # score >= threshold
    critique: str                    # what's wrong / right
    refined_prompt: str | None = None  # planner's suggested retry prompt

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunResult:
    run_id: str
    run_dir: str
    plan_path: str
    final_video: str
    qc_reports: list[QCReport] = field(default_factory=list)
    flagged_keyframes: list[str] = field(default_factory=list)  # ids that failed QC after retry

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "plan_path": self.plan_path,
            "final_video": self.final_video,
            "flagged_keyframes": self.flagged_keyframes,
            "qc_reports": [r.to_dict() for r in self.qc_reports],
        }
