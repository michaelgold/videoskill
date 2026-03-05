import json
import time
from pathlib import Path

import typer

from video_skill_extractor.chunking import (
    chunk_segments,
    chunk_segments_word_timing,
    read_chunks_jsonl,
    write_chunks_jsonl,
)
from video_skill_extractor.clips import extract_clips, read_frames_jsonl, write_clips_jsonl
from video_skill_extractor.enrich import (
    enrich_steps,
    read_frames_manifest_jsonl,
    read_steps_jsonl,
    write_enriched_steps_jsonl,
)
from video_skill_extractor.extractor import (
    extract_steps,
    read_clips_manifest_jsonl,
    write_steps_jsonl,
)
from video_skill_extractor.extractor_ai import extract_steps_from_chunks_ai
from video_skill_extractor.frame_plan import plan_frames, read_segments_jsonl, write_frames_jsonl
from video_skill_extractor.frames import (
    extract_frames_for_steps,
    write_frames_manifest_jsonl,
)
from video_skill_extractor.frames import (
    read_steps_jsonl as read_steps_for_frames,
)
from video_skill_extractor.models import Step
from video_skill_extractor.postprocess import (
    align_steps_with_transcript,
    calibrate_steps,
    normalize_steps,
    read_jsonl_rows,
    write_jsonl_rows,
)
from video_skill_extractor.providers import ping_provider
from video_skill_extractor.render import read_jsonl, render_markdown, write_markdown
from video_skill_extractor.settings import AppConfig, validate_config
from video_skill_extractor.transcribe import transcribe_video_whisper_openai
from video_skill_extractor.transcript import parse_whisper_json, write_segments_jsonl

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
    use_word_times: bool = typer.Option(False, help="Use per-word timing when available"),
) -> None:
    parsed = read_segments_jsonl(segments)
    chunks = (
        chunk_segments_word_timing(parsed, window_s=window_s, overlap_s=overlap_s)
        if use_word_times
        else chunk_segments(parsed, window_s=window_s, overlap_s=overlap_s)
    )
    write_chunks_jsonl(chunks, out)
    typer.echo(f"chunks={len(chunks)} out={out}")


@app.command("frames-extract")
def frames_extract(
    video: Path = typer.Option(..., help="Path to source video"),
    steps: Path = typer.Option(..., help="Path to steps JSONL"),
    out_dir: Path = typer.Option(..., help="Output directory for extracted frames"),
    manifest_out: Path = typer.Option(..., help="Output frames manifest JSONL"),
    sample_count: int = typer.Option(3, help="Frames sampled per step"),
) -> None:
    parsed_steps = read_steps_for_frames(steps)
    rows = extract_frames_for_steps(video, parsed_steps, out_dir=out_dir, sample_count=sample_count)
    write_frames_manifest_jsonl(rows, manifest_out)
    typer.echo(f"frame_sets={len(rows)} out_dir={out_dir} manifest={manifest_out}")


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
    mode: str = typer.Option("scaffold", help="scaffold|ai"),
    chunks: Path | None = typer.Option(
        None,
        help="Path to transcript chunks JSONL (required for ai mode)",
    ),
    config: Path = typer.Option(Path("config.json"), help="Provider config path for ai mode"),
) -> None:
    clips_by_segment = read_clips_manifest_jsonl(clips_manifest)

    error_rows: list[dict[str, object]] = []
    if mode == "ai":
        if chunks is None:
            raise typer.BadParameter("--chunks is required when --mode ai")
        cfg = AppConfig.load(config)
        parsed_chunks = read_chunks_jsonl(chunks)
        steps = extract_steps_from_chunks_ai(cfg.reasoning, parsed_chunks, error_rows=error_rows)
    else:
        parsed_segments = read_segments_jsonl(segments)
        steps = extract_steps(parsed_segments, clips_by_segment)

    write_steps_jsonl(steps, out)
    if error_rows:
        err_out = out.with_suffix(out.suffix + ".errors.jsonl")
        err_out.write_text("\n".join(json.dumps(r) for r in error_rows) + "\n", encoding="utf-8")
        typer.echo(f"parse_errors={len(error_rows)} errors_out={err_out}")
    typer.echo(f"steps={len(steps)} out={out} mode={mode}")


@app.command("steps-enrich")
def steps_enrich(
    steps: Path = typer.Option(..., help="Path to TutorialStep JSONL"),
    out: Path = typer.Option(..., help="Output enriched steps JSONL"),
    mode: str = typer.Option("heuristic", help="heuristic|ai|ai-direct"),
    config: Path = typer.Option(Path("config.json"), help="Provider config path for ai mode"),
    frames_manifest: Path | None = typer.Option(None, help="Optional step frame manifest JSONL"),
) -> None:
    parsed_steps = read_steps_jsonl(steps)
    frames_by_step = read_frames_manifest_jsonl(frames_manifest) if frames_manifest else None
    error_rows: list[dict[str, object]] = []
    start_ts = time.time()

    def _progress(evt: dict[str, object]) -> None:
        step_idx = evt.get("step_index", "?")
        total = evt.get("total_steps", "?")
        sid = evt.get("step_id", "")
        stage = evt.get("stage", "")
        elapsed = time.time() - start_ts
        typer.echo(
            f"progress step={step_idx}/{total} step_id={sid} stage={stage} "
            f"errors_so_far={len(error_rows)} elapsed_s={elapsed:.1f}"
        )

    if mode == "ai":
        cfg = AppConfig.load(config)
        rows = enrich_steps(
            parsed_steps,
            reasoning=cfg.reasoning,
            vlm=cfg.vlm,
            error_rows=error_rows,
            orchestrate_with_reasoning=True,
            frames_by_step=frames_by_step,
            progress_hook=_progress,
        )
    elif mode == "ai-direct":
        cfg = AppConfig.load(config)
        rows = enrich_steps(
            parsed_steps,
            reasoning=None,
            vlm=cfg.vlm,
            error_rows=error_rows,
            orchestrate_with_reasoning=False,
            frames_by_step=frames_by_step,
            progress_hook=_progress,
        )
    else:
        rows = enrich_steps(
            parsed_steps,
            reasoning=None,
            vlm=None,
            error_rows=error_rows,
            frames_by_step=frames_by_step,
            progress_hook=_progress,
        )
    write_enriched_steps_jsonl(rows, out)
    if error_rows:
        err_out = out.with_suffix(out.suffix + ".errors.jsonl")
        err_out.write_text("\n".join(json.dumps(r) for r in error_rows) + "\n", encoding="utf-8")
        transient_recovered = sum(1 for r in error_rows if r.get("kind") == "transient_recovered")
        unresolved_final = sum(1 for r in error_rows if r.get("kind") == "unresolved_final")
        parse_errors = sum(1 for r in error_rows if r.get("kind") == "model_parse_or_call_error")
        typer.echo(
            " ".join(
                [
                    f"parse_errors={parse_errors}",
                    f"transient_recovered={transient_recovered}",
                    f"unresolved_final={unresolved_final}",
                    f"errors_out={err_out}",
                ]
            )
        )
    typer.echo(f"enriched_steps={len(rows)} out={out} mode={mode}")




@app.command("steps-normalize")
def steps_normalize(
    steps: Path = typer.Option(..., help="Input enriched steps JSONL"),
    out: Path = typer.Option(..., help="Output normalized steps JSONL"),
) -> None:
    rows = read_jsonl_rows(steps)
    norm = normalize_steps(rows)
    write_jsonl_rows(norm, out)
    typer.echo(f"normalized_steps={len(norm)} out={out}")


@app.command("steps-align-transcript")
def steps_align_transcript(
    steps: Path = typer.Option(..., help="Input normalized/enriched steps JSONL"),
    segments: Path = typer.Option(..., help="Transcript segments JSONL"),
    out: Path = typer.Option(..., help="Output transcript-aligned steps JSONL"),
    snippet_count: int = typer.Option(2, help="Number of supporting snippets per step"),
) -> None:
    rows = read_jsonl_rows(steps)
    parsed_segments = read_segments_jsonl(segments)
    aligned = align_steps_with_transcript(rows, parsed_segments, snippet_count=snippet_count)
    write_jsonl_rows(aligned, out)
    typer.echo(f"aligned_steps={len(aligned)} out={out}")



@app.command("steps-calibrate")
def steps_calibrate(
    steps: Path = typer.Option(..., help="Input normalized/aligned steps JSONL"),
    out: Path = typer.Option(..., help="Output calibrated steps JSONL"),
    weak_conf_cap: float = typer.Option(0.25, help="Confidence cap for weak evidence summaries"),
    weak_alignment_threshold: float = typer.Option(
        0.4,
        help="Transcript alignment threshold below which confidence is downweighted",
    ),
) -> None:
    rows = read_jsonl_rows(steps)
    calibrated = calibrate_steps(
        rows,
        weak_conf_cap=weak_conf_cap,
        weak_alignment_threshold=weak_alignment_threshold,
    )
    write_jsonl_rows(calibrated, out)
    typer.echo(f"calibrated_steps={len(calibrated)} out={out}")

@app.command("markdown-render")
def markdown_render(
    steps: Path = typer.Option(..., help="Input steps/enriched steps JSONL"),
    out: Path = typer.Option(..., help="Output markdown path"),
    title: str = typer.Option("Lesson Steps"),
) -> None:
    rows = read_jsonl(steps)
    md = render_markdown(rows, title=title)
    write_markdown(md, out)
    typer.echo(f"markdown_steps={len(rows)} out={out}")


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
