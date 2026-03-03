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

## Immediate Next 10 Tasks
1. Add `OpenTimelineIO` dependency and scaffold `timeline-otio` command.
2. Freeze OTIO metadata namespace + key list in docs.
3. Implement `chapters-generate` from enriched steps.
4. Implement `clips-select` for short tutorial candidate ranking.
5. Implement `textpack-generate` (headline, bullets, emphasis terms).
6. Add `run_report.json` generation to enrichment runs.
7. Tighten `sampling_plan` prompt/output to reduce retry churn.
8. Add stage-level timeout config knobs in `config.json`.
9. Add long-class acceptance fixture and expected output checks.
10. Run full regression on `lesson1` + `zac-game` + one long-form class sample.


## P1.4 Course repurposing (YouTube course + short tutorials)

### Goals
- [ ] Convert long classes (e.g., 3-hour recordings) into:
  - a chaptered long-form course cut
  - a set of short tutorial clips
- [ ] Keep outputs editor-friendly and deterministic.

### Deliverables
- [ ] `chapters-generate` command from enriched steps:
  - outputs YouTube chapter timestamps + titles
  - optional markdown chapter sheet
- [ ] `clips-select` command:
  - ranks step windows for short-form potential
  - supports target durations (30–60s, 60–120s, 2–5m)
  - emits `shorts_manifest.jsonl`
- [ ] `textpack-generate` command:
  - per-step headline, bullets, emphasis keywords
  - on-screen text constraints for animation overlays
- [ ] `pipeline-course` orchestration command:
  - parse -> chunk -> extract -> frames -> enrich -> chapters -> clips -> textpack

### Quality gates
- [ ] Chapter coverage: >=95% of enriched steps mapped to chapter ranges.
- [ ] Shorts precision: >=80% human-accepted clips in top-ranked batch.
- [ ] Textpack readability constraints enforced (char/line limits).

---

## Execution Plan (next 3 sprints)

### Sprint 1 — OTIO + chaptering foundation
- [ ] Add `OpenTimelineIO` dependency and `timeline-otio` command.
- [ ] Freeze metadata namespace and mapping doc.
- [ ] Ship `chapters-generate` with regression tests.
- [ ] Add `run_report.json` telemetry output.

### Sprint 2 — Shorts extraction + textpack
- [ ] Implement `clips-select` scoring/ranking.
- [ ] Implement `textpack-generate` on transcript+enriched context.
- [ ] Add fixtures for long-form class input and acceptance tests.

### Sprint 3 — Editor handoff + polish
- [ ] Add `.otioz` export option and manifest bundling.
- [ ] Produce editor handoff bundle (`.otio`, manifests, markdown, clip list).
- [ ] Pilot on one 3-hour class and measure keep/delete/edit rates.
