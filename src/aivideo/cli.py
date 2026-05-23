"""`aivideo` CLI.

Commands:
- `aivideo make "<idea>" [--style ... --duration ... --aspect ... --mood ... --voice ...]`
- `aivideo photo <image>`        Upload a photo and get an asset:// URI
- `aivideo run scripts/x.py`     Run a hand-rolled script in-process
- `aivideo styles`               List available preset slugs
"""

from __future__ import annotations

import runpy
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import assets as assets_mod
from . import presets

app = typer.Typer(help="Script-driven AI video generation on Token360.")
_console = Console()


@app.command()
def make(
    idea: str = typer.Argument(..., help="One-line creative idea, e.g. 'a cat learns to surf'"),
    style: str = typer.Option(None, help="Preset slug (cyberpunk, ghibli, ...) or raw description"),
    duration: str = typer.Option(None, help="snippet | short | standard | long_form, or seconds (e.g. 30)"),
    aspect: str = typer.Option(None, help="vertical | horizontal | square"),
    mood: str = typer.Option(None, help="cheerful | melancholic | mysterious | epic | comedic | romantic | suspenseful | serene"),
    voice: str = typer.Option(None, help="warm | energetic | deep | bright | gentle | dramatic"),
    pacing: str = typer.Option(None, help="slow | normal | fast"),
    motion: str = typer.Option("video_gen", help="video_gen | kenburns"),
    qc: bool = typer.Option(True, help="Enable quality control loop"),
    portrait: str = typer.Option(None, help="Local image path OR asset:// URI for character consistency"),
    llm_model: str = typer.Option(None, help="Override planner LLM"),
    no_narration: bool = typer.Option(False, "--no-narration", help="Skip TTS narration + subtitles; use Seedance built-in ambient audio (generate_audio=true)"),
) -> None:
    """Turn a fuzzy idea into a finished mp4 under runs/<timestamp>-<slug>/."""
    from .pipelines.auto import make as run_auto

    result = run_auto(
        idea,
        style=style,
        duration=duration,
        aspect=aspect,
        mood=mood,
        voice=voice,
        pacing=pacing,
        motion=motion,
        qc_enabled=qc,
        portrait=portrait,
        llm_model=llm_model,
        no_narration=no_narration,
    )
    typer.echo(f"\nFinal video: {result.final_video}")
    typer.echo(f"Run folder:  {result.run_dir}")
    if result.flagged_keyframes:
        typer.echo(f"Flagged:     {', '.join(result.flagged_keyframes)}  (see report.md)")


@app.command()
def photo(
    path: str = typer.Argument(..., help="Local image file to upload"),
    name: str = typer.Option(None, help="Asset group name (defaults to file stem)"),
    real: bool = typer.Option(False, help="Use RealFace flow (requires H5 person verification)"),
) -> None:
    """Upload a photo to Token360 and print its asset:// URI.

    By default, creates a Virtual Portrait group (AI-character workflow,
    no human verification). Use --real to create a RealFace group, which
    prints an H5 link the person must scan on their phone within 120s
    BEFORE you upload images to the group.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise typer.BadParameter(f"Image file not found: {path}")
    group_name = name or f"aivideo-{p.stem}"

    if real:
        gid, h5 = assets_mod.create_real_face_group(group_name)
        typer.echo(f"RealFace group created: {gid}")
        if h5:
            typer.echo("\n>>> Have the person scan this H5 link within 120 seconds:")
            typer.echo(f"    {h5}\n")
            typer.echo("After verification, re-run with --group <id> to upload, or use the lower-level API.")
        else:
            typer.echo("(no H5 link returned; check Token360 console)")
        return

    typer.echo(f"Uploading {p.name} as Virtual Portrait…")
    uris = assets_mod.setup_virtual_portrait(group_name, [p])
    typer.echo(f"\n  {uris[0]}\n")
    typer.echo("Use this URI as --portrait in `aivideo make`, or pass the local path")
    typer.echo("directly — `aivideo make` will upload automatically.")


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


@app.command()
def styles() -> None:
    """Show all preset slugs you can pass to `aivideo make`."""
    catalog = presets.list_options()
    descriptors = {
        "style": presets.STYLES,
        "duration": presets.DURATIONS,
        "aspect": presets.ASPECTS,
        "mood": presets.MOODS,
        "voice": presets.VOICES,
        "pacing": presets.PACINGS,
    }
    for category in ["style", "duration", "aspect", "mood", "voice", "pacing"]:
        table = Table(title=f"--{category}", show_header=True)
        table.add_column("slug", style="bold cyan")
        table.add_column("expands to")
        for slug in catalog[category]:
            value = descriptors[category][slug]
            table.add_row(slug, str(value))
        _console.print(table)
        _console.print()


if __name__ == "__main__":
    app()
