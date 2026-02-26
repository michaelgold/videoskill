# BACKLOG.md — course-step-extractor

## Mission
Turn course recordings into **structured markdown lesson steps** (and later Slidev), with deterministic, schema-validated extraction.

## Current Status

### ✅ Done
- Repo scaffolded with TDD workflow
- `INSTRUCTIONS.md`, `Makefile`, coverage gate (`>=90%`)
- Typer CLI scaffold + starter tests
- Pydantic models scaffold
- `pydantic-ai` dependency added and verified

### ⚠️ Not started
- Transcript ingestion/parsing
- Frame timestamp planning
- PydanticAI extraction pipeline
- Markdown step renderer
- Batch processing over class folders

---

## P0 — Core pipeline (v1 markdown output)

### P0.1 Schemas
- [ ] Add models:
  - `TranscriptSegment`
  - `FrameCandidate`
  - `TutorialStep`
  - `LessonMarkdown`
- [ ] Expand `TutorialStep` with replication-critical fields:
  - `instruction_text`
  - `intent`
  - `objects_tools_settings`
  - `expected_outcome`
  - `failure_modes`
  - `confidence`
  - `step_clip_path`
- [ ] Add strict validators (timestamps, non-empty fields, enums)

### P0.2 Transcript ingestion
- [ ] `transcript parse` command
- [ ] Support Whisper JSON (first), then SRT/VTT
- [ ] Normalize to canonical segment JSONL

### P0.3 Frame planning
- [ ] `frames plan` command
- [ ] Heuristics:
  - pause boundaries
  - cue words ("now", "next", "then", "add")
  - max segment duration cap
- [ ] Emit candidate timestamps per segment (start/mid/end)
- [ ] Output step windows suitable for clip extraction (`clip_start`, `clip_end`)

### P0.4 Visual evidence clips (human inspection)
- [ ] `clips extract` command
- [ ] Generate short mp4 per step window (e.g., 3–8s)
- [ ] Persist clip paths alongside structured step outputs
- [ ] Add quick QA mode to review clips sequentially

### P0.5 Extraction
- [ ] `steps extract` command (PydanticAI-backed)
- [ ] Adapter layer around model client
- [ ] Strict structured output + retry/repair for invalid objects
- [ ] Require step fields sufficient for agent replication (action + intent + expected outcome)

### P0.6 Markdown rendering
- [ ] `markdown render` command
- [ ] Output sections:
  - title/goals
  - tools/settings
  - numbered steps
  - checkpoints
  - pitfalls
- [ ] Per-step structure should include:
  - Action
  - Why (intent)
  - Expected result
  - Failure checks
  - Clip reference/path

---

## P1 — Quality + scale

### P1.1 Validation/repair
- [ ] Deduplicate near-identical steps
- [ ] Detect missing transitions and flag
- [ ] Add confidence scoring per step

### P1.2 Batch processing
- [ ] `course run` command over directory trees
- [ ] Resumable job state + per-lesson outputs

### P1.3 Metrics
- [ ] Report:
  - segments processed
  - steps extracted
  - rejected/invalid steps
  - average confidence

---

## P2 — Presentation output

### P2.1 Slidev bridge
- [ ] Markdown-to-Slidev transformer
- [ ] Template presets (concise vs detailed)

### P2.2 Media linking
- [ ] Attach keyframe images to relevant steps
- [ ] Optional per-step thumbnails

---

## P3 — Optional optimization layer

### P3.1 Reasoning planner
- [ ] Add a reasoning-model stage to pick high-value timestamps from Whisper before Gemma extraction

### P3.2 DSPy (optional, later)
- [ ] Evaluate DSPy only after baseline extraction metrics are stable
- [ ] Use for optimization, not initial correctness

---

## Immediate Next 5 Tasks
1. Implement `TranscriptSegment` and expanded `TutorialStep` models (including intent/outcome/clip fields) with tests.
2. Add `transcript parse --input whisper.json --out segments.jsonl`.
3. Add `frames plan --segments segments.jsonl --out frames.jsonl` with clip windows.
4. Add `clips extract --video input.mp4 --frames frames.jsonl --out clips/`.
5. Scaffold `steps extract` + `markdown render` with golden snapshot tests including clip references.
