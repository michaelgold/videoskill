# video-skill-extractor

`video-skill-extractor` turns narrated videos into structured, timeline-ready skill steps.

Current pipeline supports:
- transcription (OpenAI-compatible Whisper endpoint)
- transcript parsing + chunking
- AI step extraction
- per-step frame extraction (ffmpeg)
- AI enrichment (reasoning + VLM, two-pass visual analysis)
- markdown rendering
- provider health checks

---

## 1) Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Docker (for local model services, optional)
- ffmpeg binary is handled via `imageio-ffmpeg` in this project

---

## 2) Install

```bash
cd /Users/mg/src/course-step-extractor
uv sync --dev
```

Sanity checks:

```bash
uv run ruff check .
uv run pytest -q
```

---

## 3) Model setup (local/self-hosted)

### A. Download models

```bash
./scripts/bootstrap_models.sh
```

### B. Start model stack

```bash
docker compose -f deploy/docker-compose.models.yml up -d
```

### C. Verify services are up

```bash
docker compose -f deploy/docker-compose.models.yml ps
```

---

## 4) Configure `config.json`

Create from template:

```bash
cp config.example.json config.json
```

Set the 3 provider roles:
- `transcription` → Whisper/OpenAI-compatible ASR endpoint
- `reasoning` → reasoning model endpoint
- `vlm` → vision-language model endpoint

Use served model IDs from `/v1/models` (not raw filenames unless the server exposes those as IDs).

Validate + ping:

```bash
uv run video-skill config-validate --config config.json
uv run video-skill providers-ping --config config.json --path /v1/models
```

---

## 5) CLI quick usage

```bash
uv run video-skill --help
```

Key commands:
- `transcribe`
- `transcript-parse`
- `transcript-chunk`
- `steps-extract`
- `frames-extract`
- `steps-enrich`
- `markdown-render`

---

## 6) End-to-end run (manual stages)

Example video: `datasets/demo/zac-game.mp4`

```bash
# 1) ASR
uv run video-skill transcribe \
  --video datasets/demo/zac-game.mp4 \
  --out datasets/demo/zac-game.whisper.json \
  --config config.json

# 2) Parse transcript
uv run video-skill transcript-parse \
  --input datasets/demo/zac-game.whisper.json \
  --out datasets/demo/zac-game.segments.jsonl

# 3) Chunk transcript
uv run video-skill transcript-chunk \
  --segments datasets/demo/zac-game.segments.jsonl \
  --out datasets/demo/zac-game.chunks.jsonl \
  --window-s 120 \
  --overlap-s 15

# 4) Extract steps (AI)
uv run video-skill steps-extract \
  --segments datasets/demo/zac-game.segments.jsonl \
  --clips-manifest datasets/demo/lesson1.clips.jsonl \
  --chunks datasets/demo/zac-game.chunks.jsonl \
  --mode ai \
  --config config.json \
  --out datasets/demo/zac-game.steps.ai.jsonl

# 5) Extract per-step frames for VLM grounding
uv run video-skill frames-extract \
  --video datasets/demo/zac-game.mp4 \
  --steps datasets/demo/zac-game.steps.ai.jsonl \
  --out-dir datasets/demo/frames_zac_game \
  --manifest-out datasets/demo/zac-game.frames_manifest.jsonl \
  --sample-count 2

# 6) Enrich steps (AI, two-pass visual)
uv run video-skill steps-enrich \
  --steps datasets/demo/zac-game.steps.ai.jsonl \
  --frames-manifest datasets/demo/zac-game.frames_manifest.jsonl \
  --out datasets/demo/zac-game.steps.enriched.ai.jsonl \
  --mode ai \
  --config config.json

# 7) Render markdown
uv run video-skill markdown-render \
  --steps datasets/demo/zac-game.steps.enriched.ai.jsonl \
  --out datasets/demo/zac-game.md \
  --title "Zac Game - Skill Steps"
```

---

## 7) Enrichment modes

- `--mode heuristic`
  - no model calls; deterministic baseline
- `--mode ai-direct`
  - VLM-only enrichment path
- `--mode ai`
  - reasoning + VLM orchestration (recommended)

`steps-enrich` prints progress per step/stage and summary telemetry:
- `parse_errors`
- `transient_recovered`
- `unresolved_final`

---

## 8) Testing and quality gates

```bash
make verify
```

This runs lint + tests with coverage gate (`>=90%`).

---

## 9) Output artifacts

Typical outputs:
- `*.whisper.json`
- `*.segments.jsonl`
- `*.chunks.jsonl`
- `*.steps.ai.jsonl`
- `*.frames_manifest.jsonl`
- `*.steps.enriched.ai.jsonl`
- optional `*.errors.jsonl` for parse/call telemetry

---

## 10) Next direction

The project is evolving toward a generalized video skill library with OTIO-ready timeline metadata and editor/robotics adapters.
