---
name: video-skill
description: Run the local video-skill-extractor pipeline to convert narrated videos into structured step data and enriched timeline-ready outputs. Use when a user asks to process a video into steps, run transcription/chunking/extraction/enrichment, debug model/provider connectivity, or generate markdown from extracted skills.
metadata: { "openclaw": { "emoji": "🎬", "requires": { "bins": ["uv", "git"] } } }
---

# Video Skill

Use this skill to run `video-skill-extractor` end-to-end or stage-by-stage.

## First-time setup (required)

If the repo is not present locally, clone and set it up first:

```bash
git clone https://github.com/michaelgold/videoskill.git
cd videoskill
uv sync --dev
cp config.example.json config.json
```

Then edit `config.json` for your transcription/reasoning/vlm endpoints and verify:

```bash
uv run video-skill config-validate --config config.json
uv run video-skill providers-ping --config config.json --path /v1/models
```

## Standard workflow (recommended)

From your local `video-skill-extractor` repo root (where `pyproject.toml` and `config.json` live):

1. Validate provider config:

```bash
uv run video-skill config-validate --config config.json
uv run video-skill providers-ping --config config.json --path /v1/models
```

2. Run pipeline stages:

```bash
uv run video-skill transcribe --video <video.mp4> --out <name>.whisper.json --config config.json
uv run video-skill transcript-parse --input <name>.whisper.json --out <name>.segments.jsonl
uv run video-skill transcript-chunk --segments <name>.segments.jsonl --out <name>.chunks.jsonl --window-s 120 --overlap-s 15
uv run video-skill steps-extract --segments <name>.segments.jsonl --clips-manifest <clips>.jsonl --chunks <name>.chunks.jsonl --mode ai --config config.json --out <name>.steps.ai.jsonl
uv run video-skill frames-extract --video <video.mp4> --steps <name>.steps.ai.jsonl --out-dir <frames_dir> --manifest-out <name>.frames_manifest.jsonl --sample-count 2
uv run video-skill steps-enrich --steps <name>.steps.ai.jsonl --frames-manifest <name>.frames_manifest.jsonl --out <name>.steps.enriched.ai.jsonl --mode ai --config config.json
uv run video-skill markdown-render --steps <name>.steps.enriched.ai.jsonl --out <name>.md --title "<Title>"
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
make verify
```

Only report “done” after lint/tests/coverage pass and output artifact paths are confirmed.
