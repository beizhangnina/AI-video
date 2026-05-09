"""`aivideo` CLI — convenience runner for scripts/."""

from __future__ import annotations

import runpy
from pathlib import Path

import typer

app = typer.Typer(help="Run a video script from the scripts/ directory.")


@app.command()
def run(script: str = typer.Argument(..., help="Path to a script under scripts/")) -> None:
    """Execute a video-generation script in-process."""
    p = Path(script)
    if not p.exists():
        candidate = Path("scripts") / script
        if candidate.exists():
            p = candidate
    if not p.exists():
        raise typer.BadParameter(f"Script not found: {script}")
    runpy.run_path(str(p), run_name="__main__")


@app.command()
def list() -> None:  # noqa: A001 - intentional CLI verb
    """List available scripts in ./scripts."""
    folder = Path("scripts")
    if not folder.exists():
        typer.echo("No scripts/ directory in the current working directory.")
        return
    for p in sorted(folder.glob("*.py")):
        typer.echo(p.name)


if __name__ == "__main__":
    app()
