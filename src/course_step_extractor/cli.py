from pathlib import Path

import typer

from course_step_extractor.frame_plan import plan_frames, read_segments_jsonl, write_frames_jsonl
from course_step_extractor.models import Step
from course_step_extractor.providers import ping_provider
from course_step_extractor.settings import AppConfig, validate_config
from course_step_extractor.transcript import parse_whisper_json, write_segments_jsonl

app = typer.Typer(help="Course step extraction CLI", no_args_is_help=True)


@app.command("version")
def version() -> None:
    typer.echo("0.1.0")


@app.command("sample")
def sample() -> None:
    """Emit a sample markdown step."""
    step = Step(title="Open video", description="Load the video file and transcript.")
    typer.echo(f"## {step.title}\n\n- {step.description}")


@app.command("config-validate")
def config_validate(config: Path = typer.Option(Path("config.json"))) -> None:
    ok, message = validate_config(config)
    if not ok:
        typer.echo(message)
        raise typer.Exit(1)

    payload = AppConfig.load(config)
    typer.echo(
        f"OK: transcription={payload.transcription.provider}, "
        f"reasoning={payload.reasoning.provider}, vlm={payload.vlm.provider}"
    )


@app.command("transcript-parse")
def transcript_parse(
    input: Path = typer.Option(..., help="Path to Whisper JSON transcript"),
    out: Path = typer.Option(..., help="Path to output segments JSONL"),
) -> None:
    segments = parse_whisper_json(input)
    write_segments_jsonl(segments, out)
    typer.echo(f"parsed_segments={len(segments)} out={out}")


@app.command("frames-plan")
def frames_plan(
    segments: Path = typer.Option(..., help="Path to segments JSONL"),
    out: Path = typer.Option(..., help="Path to output frame candidates JSONL"),
    clip_pad_s: float = typer.Option(1.0, help="Seconds padding around each segment"),
) -> None:
    parsed = read_segments_jsonl(segments)
    candidates = plan_frames(parsed, clip_pad_s=clip_pad_s)
    write_frames_jsonl(candidates, out)
    typer.echo(f"frame_candidates={len(candidates)} out={out}")


@app.command("providers-ping")
def providers_ping(
    config: Path = typer.Option(Path("config.json")),
    path: str = typer.Option("/"),
) -> None:
    cfg = AppConfig.load(config)
    providers = {
        "transcription": cfg.transcription,
        "reasoning": cfg.reasoning,
        "vlm": cfg.vlm,
    }
    all_ok = True
    for name, provider in providers.items():
        result = ping_provider(provider, path=path)
        status = "ok" if result["ok"] else "fail"
        typer.echo(f"{name}: {status} ({result['status_code']}) {result['url']}")
        all_ok = all_ok and bool(result["ok"])

    if not all_ok:
        raise typer.Exit(1)
