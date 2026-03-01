# BACKLOG.md — video-skill-extractor

## Mission
Build a generalized **video skill extraction library** that converts narrated video into:
1) structured skill steps,
2) visually grounded enrichment,
3) timeline-ready metadata for editors and robotics workflows.

---

## Current Status

### ✅ Shipped
- End-to-end CLI pipeline:
  - `transcribe`
  - `transcript-parse`
  - `transcript-chunk`
  - `steps-extract` (AI)
  - `frames-extract`
  - `steps-enrich` (heuristic / ai-direct / ai)
  - `markdown-render`
- PydanticAI-based model calling with explicit OpenAI-compatible provider wiring.
- Two-pass enrichment in `--mode ai`:
  - frame selection
  - signal extraction (before/after/change fields)
- Retry/backoff + jitter + telemetry:
  - `parse_errors`
  - `transient_recovered`
  - `unresolved_final`
- Stepwise progress logging for long enrich runs.
- Quality gates stable:
  - lint + tests + coverage (`>=90%`).
- Package/CLI rename complete:
  - package: `video_skill_extractor`
  - CLI: `video-skill`

---

## P0 — Reliability hardening (active)

### P0.1 Enrichment reliability
- [ ] Reduce `sampling_plan` validation churn (still largest error source).
- [ ] Improve strict structured compliance for reasoning outputs.
- [ ] Add stage-specific timeout tuning for image-heavy calls.
- [ ] Improve fallback behavior diagnostics in error manifest.

### P0.2 Observability
- [ ] Add run-level summary file (`*.run_report.json`) with per-stage stats.
- [ ] Add optional per-step latency histogram output.
- [ ] Add `--quiet-progress` toggle for CI usage.

### P0.3 Repeatability
- [ ] Add deterministic run-id/version stamping in output metadata.
- [ ] Add golden smoke fixtures for `ai` mode output shape.

---

## P1 — OTIO + editor bridge

### P1.1 OTIO foundation
- [ ] Add dependency: `OpenTimelineIO`.
- [ ] Implement `timeline-otio` command from enriched steps.
- [ ] Define and freeze metadata namespace (e.g. `com.corememory.edit.*`).
- [ ] Export `.otio` first; add `.otioz` option.

### P1.2 Edit planning artifacts
- [ ] Define `editplan` schema.
- [ ] Define `textpack` schema (headline, bullets, emphasis).
- [ ] Define `asset_manifest` schema.
- [ ] Attach template bindings and confidence metadata.

### P1.3 Resolve bridge
- [ ] Create Resolve materializer script prototype.
- [ ] Map OTIO markers/metadata -> editable title/gfx inserts.
- [ ] Add pilot template set (3 templates):
  - lower_third
  - step_callout
  - highlight_box

---

## P2 — Research track (video + narration)

### P2.1 Benchmark spine
- [ ] Build benchmark harness for narration/timeline ablations.
- [ ] Implement 4-condition ladder:
  1. video-only
  2. video+ASR
  3. +timeline structure
  4. +evidence/confidence
- [ ] Add boundary jitter robustness tests.

### P2.2 Dataset/format alignment
- [ ] Define canonical sidecar schema v1 for timeline semantics.
- [ ] Add OTIO + sidecar alignment docs for reproducibility.

---

## P3 — Robotics-oriented extension

- [ ] Add robotics semantic fields:
  - action verbs
  - object references
  - state_before/state_after
  - success signals
- [ ] Add ROS-friendly export adapter from sidecar metadata.
- [ ] Add simulation-only test harness for narrated skill videos.

---

## Immediate Next 7 Tasks
1. Add `OpenTimelineIO` dependency and scaffold `timeline-otio` command.
2. Freeze OTIO metadata namespace + key list in docs.
3. Implement `editplan` + `textpack` schema files and validators.
4. Add `run_report.json` generation to enrichment runs.
5. Tighten `sampling_plan` prompt/output to reduce retry churn.
6. Add stage-level timeout config knobs in `config.json`.
7. Run full regression on `lesson1` and `zac-game` and record baseline telemetry.
