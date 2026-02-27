from pathlib import Path

import typer

from course_step_extractor.chunking import chunk_segments, write_chunks_jsonl
from course_step_extractor.clips import extract_clips, read_frames_jsonl, write_clips_jsonl
from course_step_extractor.extractor import (
    extract_steps,
    read_clips_manifest_jsonl,
    write_steps_jsonl,
)
from course_step_extractor.frame_plan import plan_frames, read_segments_jsonl, write_frames_jsonl
from course_step_extractor.models import Step
from course_step_extractor.providers import ping_provider
from course_step_extractor.settings import AppConfig, validate_config
from course_step_extractor.transcribe import transcribe_video_whisper_openai
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


@app.command("transcribe")
def transcribe(
    video: Path = typer.Option(..., help="Path to source video file"),
    out: Path = typer.Option(..., help="Output Whisper JSON path"),
    config: Path = typer.Option(Path("config.json"), help="Provider config path"),
) -> None:
    cfg = AppConfig.load(config)
    payload = transcribe_video_whisper_openai(cfg.transcription, video, out)
    seg_count = len(payload.get("segments", [])) if isinstance(payload, dict) else 0
    typer.echo(f"transcribed_segments={seg_count} out={out}")


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


@app.command("transcript-chunk")
def transcript_chunk(
    segments: Path = typer.Option(..., help="Path to transcript segments JSONL"),
    out: Path = typer.Option(..., help="Output chunk JSONL"),
    window_s: float = typer.Option(120.0, help="Chunk window in seconds"),
    overlap_s: float = typer.Option(15.0, help="Overlap between consecutive chunks"),
) -> None:
    parsed = read_segments_jsonl(segments)
    chunks = chunk_segments(parsed, window_s=window_s, overlap_s=overlap_s)
    write_chunks_jsonl(chunks, out)
    typer.echo(f"chunks={len(chunks)} out={out}")


@app.command("clips-extract")
def clips_extract(
    video: Path = typer.Option(..., help="Path to source video"),
    frames: Path = typer.Option(..., help="Path to frame candidates JSONL"),
    out_dir: Path = typer.Option(..., help="Output directory for clip mp4 files"),
    manifest_out: Path = typer.Option(..., help="Output clips JSONL manifest"),
    reencode: bool = typer.Option(True, help="Re-encode clips for compatibility"),
) -> None:
    candidates = read_frames_jsonl(frames)
    rows = extract_clips(video, candidates, out_dir=out_dir, reencode=reencode)
    write_clips_jsonl(rows, manifest_out)
    typer.echo(f"clips={len(rows)} out_dir={out_dir} manifest={manifest_out}")


@app.command("steps-extract")
def steps_extract(
    segments: Path = typer.Option(..., help="Path to transcript segments JSONL"),
    clips_manifest: Path = typer.Option(..., help="Path to clips manifest JSONL"),
    out: Path = typer.Option(..., help="Output TutorialStep JSONL"),
) -> None:
    parsed_segments = read_segments_jsonl(segments)
    clips_by_segment = read_clips_manifest_jsonl(clips_manifest)
    steps = extract_steps(parsed_segments, clips_by_segment)
    write_steps_jsonl(steps, out)
    typer.echo(f"steps={len(steps)} out={out}")


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
