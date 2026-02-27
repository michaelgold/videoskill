from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from course_step_extractor.ai_adapter import run_structured
from course_step_extractor.models import TutorialStep
from course_step_extractor.settings import ProviderConfig


@dataclass
class EnrichmentPlan:
    sample_count: int
    rationale: str


class SamplingPlanModel(BaseModel):
    sample_count: int = Field(ge=2, le=10)
    rationale: str = Field(min_length=1)


class VlmJudgeModel(BaseModel):
    motion_detected: bool
    alignment_ok: bool | None = None
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


def read_steps_jsonl(path: Path) -> list[TutorialStep]:
    steps: list[TutorialStep] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        steps.append(TutorialStep.model_validate(json.loads(line)))
    return steps


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


def reasoning_plan_with_model(provider: ProviderConfig, step: TutorialStep) -> EnrichmentPlan:
    system = (
        "You plan frame sampling for video-step visual verification. "
        "Return JSON {sample_count:int, rationale:str}."
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
        parsed = run_structured(provider, system, user, SamplingPlanModel)
        n = int(parsed.sample_count)
        return EnrichmentPlan(sample_count=max(2, min(10, n)), rationale=parsed.rationale)
    except Exception:
        return plan_sampling_for_step(step)


def vlm_motion_judge_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    timestamps: list[float],
) -> dict[str, object]:
    system = (
        "You judge whether tutorial step motion/result likely occurred based on provided timestamps context. "
        "Return JSON {motion_detected:bool, alignment_ok:bool|null, summary:str, confidence:0..1}."
    )
    user = json.dumps(
        {
            "step_id": step.step_id,
            "instruction_text": step.instruction_text,
            "intent": step.intent,
            "expected_outcome": step.expected_outcome,
            "timestamps": timestamps,
        }
    )
    try:
        parsed = run_structured(provider, system, user, VlmJudgeModel)
        return parsed.model_dump()
    except Exception:
        return {
            "motion_detected": False,
            "alignment_ok": None,
            "summary": "vlm_unavailable_or_parse_error",
            "confidence": 0.0,
        }


def enrich_steps(
    steps: list[TutorialStep],
    reasoning: ProviderConfig | None = None,
    vlm: ProviderConfig | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in steps:
        plan = reasoning_plan_with_model(reasoning, step) if reasoning else plan_sampling_for_step(step)
        ts = sample_timestamps(step, plan.sample_count)
        judge = vlm_motion_judge_with_model(vlm, step, ts) if vlm else {
            "motion_detected": None,
            "alignment_ok": None,
            "summary": "vlm_not_configured",
            "confidence": 0.0,
        }

        rows.append(
            {
                **step.model_dump(),
                "enrichment": {
                    "sampling": {
                        "count": plan.sample_count,
                        "rationale": plan.rationale,
                        "timestamps": ts,
                    },
                    "vlm_judgement": judge,
                },
            }
        )
    return rows


def write_enriched_steps_jsonl(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
