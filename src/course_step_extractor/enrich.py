from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
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


class FinalJudgeModel(BaseModel):
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
        parsed = run_structured(
            provider,
            system,
            user,
            SamplingPlanModel,
            max_retries=2,
            error_rows=error_rows,
            error_context={"step_id": step.step_id, "stage": "sampling_plan"},
        )
        n = int(parsed.sample_count)
        return EnrichmentPlan(sample_count=max(2, min(10, n)), rationale=parsed.rationale)
    except Exception:
        return plan_sampling_for_step(step)


def vlm_motion_judge_with_model(
    provider: ProviderConfig,
    step: TutorialStep,
    timestamps: list[float],
    frame_paths: list[str],
    error_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    endpoint = str(provider.base_url).rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = provider.api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    system = (
        "You are a vision model judging if a tutorial step visually occurred. "
        "Return strict JSON: {motion_detected:boolean, alignment_ok:boolean|null, summary:string, confidence:number_0_to_1}."
    )
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": json.dumps(
                {
                    "step_id": step.step_id,
                    "instruction_text": step.instruction_text,
                    "intent": step.intent,
                    "expected_outcome": step.expected_outcome,
                    "timestamps": timestamps,
                    "frame_count": len(frame_paths),
                }
            ),
        }
    ]

    for p in frame_paths[:10]:
        try:
            data_url = _data_url_for_image(Path(p))
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        except Exception as exc:  # noqa: BLE001
            if error_rows is not None:
                error_rows.append({"kind": "frame_read_error", "step_id": step.step_id, "path": p, "error": str(exc)})

    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }

    try:
        with httpx.Client(timeout=provider.timeout_s) as client:
            res = client.post(endpoint, headers=headers, json=payload)
            res.raise_for_status()
            body = res.json()

        raw = body["choices"][0]["message"]["content"]
        if isinstance(raw, list):
            text = " ".join(str(x.get("text", "")) for x in raw if isinstance(x, dict))
        else:
            text = str(raw)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = VlmJudgeModel.model_validate(json.loads(text))
        return parsed.model_dump()
    except Exception as exc:  # noqa: BLE001
        if error_rows is not None:
            error_rows.append(
                {
                    "kind": "model_parse_or_call_error",
                    "provider": provider.provider,
                    "model": provider.model,
                    "stage": "vlm_judge",
                    "step_id": step.step_id,
                    "error": str(exc),
                }
            )
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
        "Given step context, timestamps, and raw VLM judgement, return a normalized final judgement."
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
            max_retries=2,
            error_rows=error_rows,
            error_context={"step_id": step.step_id, "stage": "reasoning_finalize"},
        )
        return parsed.model_dump()
    except Exception:
        return raw_judge


def enrich_steps(
    steps: list[TutorialStep],
    reasoning: ProviderConfig | None = None,
    vlm: ProviderConfig | None = None,
    error_rows: list[dict[str, object]] | None = None,
    orchestrate_with_reasoning: bool = True,
    frames_by_step: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for step in steps:
        plan = (
            reasoning_plan_with_model(reasoning, step, error_rows=error_rows)
            if reasoning
            else plan_sampling_for_step(step)
        )
        ts = sample_timestamps(step, plan.sample_count)
        judge = (
            vlm_motion_judge_with_model(vlm, step, ts, error_rows=error_rows)
            if vlm
            else {
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
                        "frame_paths": frame_paths,
                    },
                    "vlm_judgement": judge,
                },
            }
        )
    return rows


def write_enriched_steps_jsonl(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
