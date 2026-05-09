"""`aivideo` CLI.

Two commands:
- `aivideo make "<idea>"`     One-shot: idea -> Plan -> agents -> mp4
- `aivideo run scripts/x.py`  Run a hand-rolled script in-process
"""

from __future__ import annotations

import runpy
from pathlib import Path

import typer

app = typer.Typer(help="Script-driven AI video generation on Token360.")


@app.command()
def make(
    idea: str = typer.Argument(..., help="One-line creative idea, e.g. 'a cat learns to surf'"),
    motion: str = typer.Option("video_gen", help="video_gen | kenburns"),
    qc: bool = typer.Option(True, help="Enable quality control loop"),
    portrait: str | None = typer.Option(None, help="asset:// URI for character consistency"),
    llm_model: str | None = typer.Option(None, help="Override planner LLM"),
) -> None:
    """Turn a fuzzy idea into a finished mp4 under runs/<timestamp>-<slug>/."""
    from .pipelines.auto import make as run_auto

    result = run_auto(
        idea,
        motion=motion,
        qc_enabled=qc,
        portrait=portrait,
        llm_model=llm_model,
    )
    typer.echo(f"\nFinal video: {result.final_video}")
    typer.echo(f"Run folder:  {result.run_dir}")
    if result.flagged_keyframes:
        typer.echo(f"Flagged:     {', '.join(result.flagged_keyframes)}  (see report.md)")


@app.command()
def run(script: str = typer.Argument(..., help="Path to a script under scripts/")) -> None:
    """Execute a hand-written video-generation script in-process."""
    p = Path(script)
    if not p.exists():
        candidate = Path("scripts") / script
        if candidate.exists():
            p = candidate
    if not p.exists():
        raise typer.BadParameter(f"Script not found: {script}")
    runpy.run_path(str(p), run_name="__main__")


@app.command(name="list")
def list_scripts() -> None:
    """List available scripts in ./scripts."""
    folder = Path("scripts")
    if not folder.exists():
        typer.echo("No scripts/ directory in the current working directory.")
        return
    for p in sorted(folder.glob("*.py")):
        typer.echo(p.name)


if __name__ == "__main__":
    app()
