---
name: video-skill
description: Run the video-skill pipeline to convert narrated videos into structured step data and enriched timeline-ready outputs. Use when a user asks to process a video into steps, run transcription/chunking/extraction/enrichment, debug provider connectivity, or generate markdown from extracted skills.
metadata: { "openclaw": { "emoji": "🎬", "requires": { "bins": ["uv", "git"] } } }
---

# Video Skill

Use this skill to run `video-skill` end-to-end or stage-by-stage.

## First-time setup (no repo clone required)

Install the latest CLI from GitHub using `uv`:

```bash
uv tool install --upgrade git+https://github.com/michaelgold/videoskill.git
```

Create a working directory and config:

```bash
mkdir -p ~/video-skill-work
cd ~/video-skill-work
cp /path/to/config.example.json config.json
```

If you already have a configured `config.json`, use that path directly in commands.

Verify providers before processing:

```bash
video-skill config-validate --config config.json
video-skill providers-ping --config config.json --path /v1/models
```

## Standard workflow (recommended)

Run from your working directory where `config.json` and data paths are valid.

```bash
video-skill transcribe --video <video.mp4> --out <name>.whisper.json --config config.json
video-skill transcript-parse --input <name>.whisper.json --out <name>.segments.jsonl
video-skill transcript-chunk --segments <name>.segments.jsonl --out <name>.chunks.jsonl --window-s 120 --overlap-s 15
video-skill steps-extract --segments <name>.segments.jsonl --clips-manifest <clips>.jsonl --chunks <name>.chunks.jsonl --mode ai --config config.json --out <name>.steps.ai.jsonl
video-skill frames-extract --video <video.mp4> --steps <name>.steps.ai.jsonl --out-dir <frames_dir> --manifest-out <name>.frames_manifest.jsonl --sample-count 2
video-skill steps-enrich --steps <name>.steps.ai.jsonl --frames-manifest <name>.frames_manifest.jsonl --out <name>.steps.enriched.ai.jsonl --mode ai --config config.json
video-skill markdown-render --steps <name>.steps.enriched.ai.jsonl --out <name>.md --title "<Title>"
```

## Modes

- `--mode heuristic`: deterministic, no model calls
- `--mode ai-direct`: VLM-centric enrichment
- `--mode ai`: reasoning + VLM orchestration (default for quality)

Prefer `--mode ai` unless user asks for debugging or reduced model usage.

## Reliability and diagnostics

`steps-enrich` emits:
- per-step progress logs
- summary metrics: `parse_errors`, `transient_recovered`, `unresolved_final`
- detailed `*.errors.jsonl` when any errors occur

If runs fail unexpectedly:
1. re-run `providers-ping`
2. inspect `*.errors.jsonl` by stage (`sampling_plan`, `vlm_judge`, `vlm_select_frames`, `vlm_signal_pass`, `reasoning_finalize`)
3. verify endpoint DNS/host reachability

## Validation gate before claiming success

Always run:

```bash
video-skill --help
```

Use `make verify` only when working from the source repo.
