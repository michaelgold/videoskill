from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from video_skill_extractor.ai_adapter import run_structured
from video_skill_extractor.chunking import TranscriptChunk
from video_skill_extractor.models import TutorialStep
from video_skill_extractor.settings import ProviderConfig


class ChunkStep(BaseModel):
    instruction_text: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class ChunkStepResponse(BaseModel):
    steps: list[ChunkStep] = Field(default_factory=list)


def _call_reasoning_chunk(
    provider: ProviderConfig,
    chunk: TranscriptChunk,
    error_rows: list[dict[str, Any]] | None = None,
) -> ChunkStepResponse:
    system = (
        "You extract concise tutorial steps from transcript chunks. "
        "Return structured output with fields: instruction_text, intent, expected_outcome, "
        "start_s, end_s, confidence."
    )
    user = {
        "chunk_id": chunk.chunk_id,
        "chunk_start_s": chunk.start_s,
        "chunk_end_s": chunk.end_s,
        "segment_ids": chunk.segment_ids,
        "text": chunk.text,
    }
    return run_structured(
        provider,
        system,
        json.dumps(user),
        ChunkStepResponse,
        max_retries=5,
        error_rows=error_rows,
        error_context={"chunk_id": chunk.chunk_id, "stage": "chunk_extract"},
    )


def extract_steps_from_chunks_ai(
    provider: ProviderConfig,
    chunks: list[TranscriptChunk],
    error_rows: list[dict[str, Any]] | None = None,
) -> list[TutorialStep]:
    steps: list[TutorialStep] = []
    idx = 1
    for chunk in chunks:
        try:
            response = _call_reasoning_chunk(provider, chunk, error_rows=error_rows)
        except Exception as exc:  # noqa: BLE001
            if error_rows is not None:
                error_rows.append(
                    {
                        "kind": "chunk_skipped_after_retries",
                        "chunk_id": chunk.chunk_id,
                        "error": str(exc),
                    }
                )
            continue

        for s in response.steps:
            start_s = max(chunk.start_s, min(s.start_s, chunk.end_s))
            end_s = max(start_s, min(s.end_s, chunk.end_s))
            steps.append(
                TutorialStep(
                    step_id=f"step_{idx}",
                    source_segment_id=chunk.segment_ids[0] if chunk.segment_ids else chunk.chunk_id,
                    start_s=start_s,
                    end_s=end_s,
                    clip_start_s=max(0.0, start_s - 1.0),
                    clip_end_s=end_s + 1.0,
                    instruction_text=s.instruction_text,
                    intent=s.intent,
                    expected_outcome=s.expected_outcome,
                    confidence=s.confidence,
                )
            )
            idx += 1

    # lightweight deterministic dedupe by normalized instruction text
    deduped: list[TutorialStep] = []
    seen: set[str] = set()
    for step in sorted(steps, key=lambda x: (x.start_s, x.end_s, x.step_id)):
        key = " ".join(step.instruction_text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(step)

    # re-index after dedupe
    for i, step in enumerate(deduped, start=1):
        step.step_id = f"step_{i}"

    return deduped
