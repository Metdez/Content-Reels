"""Content Machine CLI.

  content-machine ingest <video>   # phase 1: transcribe
  content-machine select <job_id>  # phase 2: pick clips (added in phase 2)
  content-machine render <job_id>  # phase 3: cut + caption (added in phase 3)
  content-machine serve            # phase 4: localhost UI (added in phase 4)
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Local-first LinkedIn video clipper.")


@app.callback()
def main() -> None:
    """Local-first LinkedIn video clipper — transcribe, select, render."""


@app.command()
def ingest(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Local video file"),
    model: str = typer.Option(None, "--model", "-m", help="whisper model (default: base.en)"),
    no_vad: bool = typer.Option(False, "--no-vad", help="Disable silence/hallucination filter"),
    force: bool = typer.Option(False, "--force", help="Re-transcribe even if cached"),
    language: str = typer.Option(None, "--language", "-l", help="Force language (e.g. en)"),
):
    """Transcribe a video into data/<job_id>/transcript.json."""
    from . import transcribe as t

    typer.echo(f"→ Ingesting {video.name} ...")
    job = t.transcribe(video, model=model, vad=not no_vad, force=force, language=language)
    transcript = job.transcript_path
    typer.echo(f"✓ Job {job.job_id}")
    typer.echo(f"  data dir:   {job.data_dir}")
    typer.echo(f"  transcript: {transcript}")
    if transcript.exists():
        import json
        data = json.loads(transcript.read_text())
        typer.echo(f"  language:   {data.get('language')}")
        typer.echo(f"  duration:   {data.get('duration', 0):.1f}s")
        typer.echo(f"  segments:   {len(data.get('segments', []))}"
                   + (f" (VAD dropped {data['vad_dropped']})" if data.get('vad_dropped') else ""))


if __name__ == "__main__":
    app()
