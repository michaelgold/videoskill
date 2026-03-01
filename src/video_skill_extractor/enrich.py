from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from video_skill_extractor.ai_adapter import run_structured, run_structured_with_images
from video_skill_extractor.models import TutorialStep
from video_skill_extractor.settings import ProviderConfig


@dataclass
class EnrichmentPlan:
    sample_count: int
    rationale: str


class SamplingPlanModel(BaseModel):
    sample_count: int | str
    rationale: str | None = None


class VlmJudgeModel(BaseModel):
    motion_detected: bool
    alignment_ok: bool | None = None
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class FinalJudgeModel(BaseModel):
    motion_detected: bool
    alignment_ok: bool | None = None
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class VlmFrameSelectionModel(BaseModel):
    selected_indices: list[int] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class VlmSignalModel(BaseModel):
    summary: str = Field(min_length=1)
    detected_events: list[str] = Field(min_length=1)
    observations: list[str] = Field(min_length=1)
    before_observations: list[str] = Field(min_length=1)
    after_observations: list[str] = Field(min_length=1)
    changes_detected: list[str] = Field(min_length=1)
    unchanged_signals: list[str] = Field(default_factory=list)
    change_confidence: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


def read_steps_jsonl(path: Path) -> list[TutorialStep]:
    steps: list[TutorialStep] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        steps.append(TutorialStep.model_validate(json.loads(line)))
    return steps


def read_frames_manifest_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        step_id = str(payload.get("step_id", ""))
        if not step_id:
            continue
        rows[step_id] = payload
    return rows


def _data_url_for_image(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/jpeg"
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".webp":
        mime = "image/webp"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _duration(step: TutorialStep) -> float:
    return max(0.0, step.end_s - step.start_s)


def plan_sampling_for_step(step: TutorialStep) -> EnrichmentPlan:
    d = _duration(step)
    text = (step.instruction_text + " " + step.intent).lower()

    if d < 8:
        n = 2
    elif d < 20:
        n = 3
    elif d < 45:
        n = 4
    elif d < 90:
        n = 6
    else:
        n = 8

    motion_tokens = ("rotate", "align", "move", "translate", "scale", "pose", "deform")
    if any(tok in text for tok in motion_tokens):
        n += 1

    cue_tokens = ("then", "next", "now", "switch")
    cue_hits = sum(text.count(tok) for tok in cue_tokens)
    if cue_hits > 0:
        n += min(2, cue_hits)

    n = max(2, min(10, n))
    return EnrichmentPlan(sample_count=n, rationale=f"duration={d:.1f}s motion/cues adjusted")


def sample_timestamps(step: TutorialStep, count: int) -> list[float]:
    start = step.clip_start_s
    end = step.clip_end_s
    if count <= 1 or end <= start:
        return [start]
    span = end - start
    return [round(start + span * (i / (count - 1)), 3) for i in range(count)]


def reasoning_plan_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    error_rows: list[dict[str, object]] | None = None,
) -> EnrichmentPlan:
    system = (
        "You plan frame sampling for video-step visual verification. "
        "Return strict JSON with sample_count only (2 to 10). "
        "Optional rationale must be short."
    )
    user = json.dumps(
        {
            "step_id": step.step_id,
            "instruction_text": step.instruction_text,
            "intent": step.intent,
            "start_s": step.start_s,
            "end_s": step.end_s,
            "clip_start_s": step.clip_start_s,
            "clip_end_s": step.clip_end_s,
        }
    )
    try:
        parsed = run_structured(
            provider,
            system,
            user,
            SamplingPlanModel,
            max_retries=5,
            error_rows=error_rows,
            error_context={"step_id": step.step_id, "stage": "sampling_plan"},
        )
        raw_count = parsed.sample_count
        if isinstance(raw_count, str):
            raw_count = raw_count.strip()
            if raw_count.isdigit():
                n = int(raw_count)
            else:
                n = int(float(raw_count))
        else:
            n = int(raw_count)
        n = max(2, min(10, n))
        rationale = (parsed.rationale or "model_plan").strip()[:140]
        return EnrichmentPlan(sample_count=n, rationale=rationale or "model_plan")
    except Exception:
        return plan_sampling_for_step(step)


def _chat_with_images(
    provider: ProviderConfig,
    system: str,
    payload_context: dict[str, Any],
    frame_paths: list[str],
    output_model: type[BaseModel],
    *,
    step_id: str,
    stage: str,
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, Any] | None:
    image_urls: list[str] = []
    for p in frame_paths[:10]:
        try:
            image_urls.append(_data_url_for_image(Path(p)))
        except Exception as exc:  # noqa: BLE001
            if error_rows is not None:
                error_rows.append(
                    {
                        "kind": "frame_read_error",
                        "step_id": step_id,
                        "path": p,
                        "stage": stage,
                        "error": str(exc),
                    }
                )
    try:
        parsed = run_structured_with_images(
            provider,
            system,
            json.dumps(payload_context),
            image_urls,
            output_model,
            max_retries=5,
            error_rows=error_rows,
            error_context={"step_id": step_id, "stage": stage},
        )
        return parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)
    except Exception:
        return None


def vlm_select_frames_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    timestamps: list[float],
    frame_paths: list[str],
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    if not frame_paths:
        return {"selected_indices": [], "rationale": "no_frames"}
    payload = {
        "task": "Select most informative evidence frames for judging completion.",
        "step_id": step.step_id,
        "instruction_text": step.instruction_text,
        "expected_outcome": step.expected_outcome,
        "timestamps": timestamps,
        "frames": [{"index": i, "path": p} for i, p in enumerate(frame_paths)],
    }
    system = (
        "Choose 1-3 best frame indices for evidence. Return JSON "
        "{selected_indices:[int], rationale:str}."
    )
    out = _chat_with_images(
        provider,
        system,
        payload,
        frame_paths,
        VlmFrameSelectionModel,
        step_id=step.step_id,
        stage="vlm_select_frames",
        error_rows=error_rows,
    )
    return out or {
        "selected_indices": list(range(min(3, len(frame_paths)))),
        "rationale": "fallback_top_frames",
    }


def vlm_signal_pass_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    selected_indices: list[int],
    frame_paths: list[str],
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    selected = [frame_paths[i] for i in selected_indices if 0 <= i < len(frame_paths)]
    if not selected:
        selected = frame_paths[:2]
    payload = {
        "task": "Extract concrete visual evidence of step completion.",
        "step_id": step.step_id,
        "instruction_text": step.instruction_text,
        "intent": step.intent,
        "expected_outcome": step.expected_outcome,
        "selected_indices": selected_indices,
    }
    system = (
        "Analyze selected frames and return STRICT JSON with non-empty arrays for "
        "detected_events, observations, before_observations, after_observations, changes_detected. "
        "Include unchanged_signals (can be empty), change_confidence and confidence. "
        "Focus on what changed between frames."
    )
    out = _chat_with_images(
        provider,
        system,
        payload,
        selected,
        VlmSignalModel,
        step_id=step.step_id,
        stage="vlm_signal_pass",
        error_rows=error_rows,
    )
    return out or {
        "summary": "signal_pass_unavailable",
        "detected_events": [],
        "observations": [],
        "before_observations": [],
        "after_observations": [],
        "changes_detected": [],
        "unchanged_signals": [],
        "change_confidence": 0.0,
        "confidence": 0.0,
    }


def vlm_motion_judge_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    timestamps: list[float],
    frame_paths: list[str],
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    system = (
        "You are a vision model judging if a tutorial step visually occurred. "
        "Return strict JSON with fields: motion_detected, alignment_ok, summary, confidence."
    )
    payload = {
        "step_id": step.step_id,
        "instruction_text": step.instruction_text,
        "intent": step.intent,
        "expected_outcome": step.expected_outcome,
        "timestamps": timestamps,
        "frame_count": len(frame_paths),
    }
    out = _chat_with_images(
        provider,
        system,
        payload,
        frame_paths,
        VlmJudgeModel,
        step_id=step.step_id,
        stage="vlm_judge",
        error_rows=error_rows,
    )
    if out is not None:
        return out
    return {
        "motion_detected": False,
        "alignment_ok": None,
        "summary": "vlm_unavailable_or_parse_error",
        "confidence": 0.0,
    }


def reasoning_finalize_judgement(
    provider: ProviderConfig,
    step: TutorialStep,
    timestamps: list[float],
    raw_judge: dict[str, object],
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    system = (
        "You are a quality gate for tutorial-step verification. "
        "Given step context, timestamps, and raw VLM judgement, normalize final judgement."
    )
    user = json.dumps(
        {
            "step_id": step.step_id,
            "instruction_text": step.instruction_text,
            "intent": step.intent,
            "expected_outcome": step.expected_outcome,
            "timestamps": timestamps,
            "raw_vlm_judgement": raw_judge,
        }
    )
    try:
        parsed = run_structured(
            provider,
            system,
            user,
            FinalJudgeModel,
            max_retries=5,
            error_rows=error_rows,
            error_context={"step_id": step.step_id, "stage": "reasoning_finalize"},
        )
        return parsed.model_dump()
    except Exception:
        return raw_judge


def _emit_progress(
    progress_hook: Callable[[dict[str, object]], None] | None,
    *,
    idx: int,
    total_steps: int,
    step_id: str,
    stage: str,
    selected: int | None = None,
) -> None:
    if progress_hook is None:
        return
    payload: dict[str, object] = {
        "step_index": idx,
        "total_steps": total_steps,
        "step_id": step_id,
        "stage": stage,
    }
    if selected is not None:
        payload["selected"] = selected
    progress_hook(payload)


def enrich_steps(
    steps: list[TutorialStep],
    reasoning: ProviderConfig | None = None,
    vlm: ProviderConfig | None = None,
    error_rows: list[dict[str, object]] | None = None,
    orchestrate_with_reasoning: bool = True,
    frames_by_step: dict[str, dict[str, Any]] | None = None,
    progress_hook: Callable[[dict[str, object]], None] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    total_steps = len(steps)
    for idx, step in enumerate(steps, start=1):
        _emit_progress(
            progress_hook,
            idx=idx,
            total_steps=total_steps,
            step_id=step.step_id,
            stage="sampling_plan_start",
        )
        plan = (
            reasoning_plan_with_model(reasoning, step, error_rows=error_rows)
            if reasoning
            else plan_sampling_for_step(step)
        )
        ts = sample_timestamps(step, plan.sample_count)
        _emit_progress(
            progress_hook,
            idx=idx,
            total_steps=total_steps,
            step_id=step.step_id,
            stage="sampling_plan_done",
        )

        frame_paths: list[str] = []
        if frames_by_step is not None:
            frame_paths = [
                str(p) for p in frames_by_step.get(step.step_id, {}).get("frame_paths", [])
            ]

        if vlm:
            _emit_progress(
                progress_hook,
                idx=idx,
                total_steps=total_steps,
                step_id=step.step_id,
                stage="vlm_judge_start",
            )
            judge = vlm_motion_judge_with_model(
                vlm,
                step,
                ts,
                frame_paths=frame_paths,
                error_rows=error_rows,
            )
            _emit_progress(
                progress_hook,
                idx=idx,
                total_steps=total_steps,
                step_id=step.step_id,
                stage="vlm_judge_done",
            )
            signal_pass: dict[str, Any] | None = None
            selected_indices: list[int] = []
            if reasoning and orchestrate_with_reasoning and frame_paths:
                _emit_progress(
                    progress_hook,
                    idx=idx,
                    total_steps=total_steps,
                    step_id=step.step_id,
                    stage="vlm_select_frames_start",
                )
                selection = vlm_select_frames_with_model(
                    vlm,
                    step,
                    ts,
                    frame_paths,
                    error_rows=error_rows,
                )
                selected_indices = [int(i) for i in selection.get("selected_indices", [])]
                _emit_progress(
                    progress_hook,
                    idx=idx,
                    total_steps=total_steps,
                    step_id=step.step_id,
                    stage="vlm_select_frames_done",
                    selected=len(selected_indices),
                )
                _emit_progress(
                    progress_hook,
                    idx=idx,
                    total_steps=total_steps,
                    step_id=step.step_id,
                    stage="vlm_signal_pass_start",
                )
                signal_pass = vlm_signal_pass_with_model(
                    vlm,
                    step,
                    selected_indices,
                    frame_paths,
                    error_rows=error_rows,
                )
                _emit_progress(
                    progress_hook,
                    idx=idx,
                    total_steps=total_steps,
                    step_id=step.step_id,
                    stage="vlm_signal_pass_done",
                )
                if signal_pass.get("summary"):
                    judge["summary"] = str(signal_pass["summary"])
                if signal_pass.get("confidence") is not None:
                    judge["confidence"] = float(signal_pass["confidence"])
                judge["signal_events"] = signal_pass.get("detected_events", [])
                judge["signal_observations"] = signal_pass.get("observations", [])
                judge["changes_detected"] = signal_pass.get("changes_detected", [])
                judge["change_confidence"] = signal_pass.get("change_confidence", 0.0)
            else:
                signal_pass = None
        else:
            judge = {
                "motion_detected": None,
                "alignment_ok": None,
                "summary": "vlm_not_configured",
                "confidence": 0.0,
            }
            selected_indices = []
            signal_pass = None

        if reasoning and orchestrate_with_reasoning:
            _emit_progress(
                progress_hook,
                idx=idx,
                total_steps=total_steps,
                step_id=step.step_id,
                stage="reasoning_finalize_start",
            )
            judge = reasoning_finalize_judgement(
                reasoning,
                step,
                ts,
                judge,
                error_rows=error_rows,
            )
            _emit_progress(
                progress_hook,
                idx=idx,
                total_steps=total_steps,
                step_id=step.step_id,
                stage="reasoning_finalize_done",
            )

        rows.append(
            {
                **step.model_dump(),
                "enrichment": {
                    "sampling": {
                        "count": plan.sample_count,
                        "rationale": plan.rationale,
                        "timestamps": ts,
                        "frame_paths": frame_paths,
                    },
                    "vlm_judgement": judge,
                    "frame_selection": {"selected_indices": selected_indices},
                    "signal_pass": signal_pass,
                },
            }
        )
        _emit_progress(
            progress_hook, idx=idx, total_steps=total_steps, step_id=step.step_id, stage="step_done"
        )

    return rows


def write_enriched_steps_jsonl(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
