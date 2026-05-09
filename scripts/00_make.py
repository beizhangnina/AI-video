"""From-idea-to-video entry point.

Run:
    python scripts/00_make.py "your fuzzy idea here"

Or via the installed CLI:
    aivideo make "your fuzzy idea here"

Output lands in runs/<timestamp>-<slug>/final.mp4 with the plan, every
intermediate artifact, every QC report, and a human-readable report.md.
"""

from __future__ import annotations

import sys

from aivideo.pipelines.auto import make


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/00_make.py \"<your idea>\"", file=sys.stderr)
        sys.exit(2)
    idea = " ".join(sys.argv[1:])
    result = make(idea)
    print(f"\nFinal: {result.final_video}")
    print(f"Run:   {result.run_dir}")
    if result.flagged_keyframes:
        print(f"Flagged: {', '.join(result.flagged_keyframes)} (see report.md)")


if __name__ == "__main__":
    main()
