from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from course_step_extractor.chunking import TranscriptChunk
from course_step_extractor.models import TutorialStep
from course_step_extractor.settings import ProviderConfig


class ChunkStep(BaseModel):
    instruction_text: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    expected_outcome: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class ChunkStepResponse(BaseModel):
    steps: list[ChunkStep] = Field(default_factory=list)


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def _call_reasoning_chunk(provider: ProviderConfig, chunk: TranscriptChunk) -> ChunkStepResponse:
    endpoint = str(provider.base_url).rstrip("/") + "/v1/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = provider.api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    system = (
        "You extract concise tutorial steps from transcript chunks. "
        "Return ONLY JSON with schema: "
        "{\"steps\":[{instruction_text,intent,expected_outcome,start_s,end_s,confidence}]}."
    )
    user = {
        "chunk_id": chunk.chunk_id,
        "chunk_start_s": chunk.start_s,
        "chunk_end_s": chunk.end_s,
        "segment_ids": chunk.segment_ids,
        "text": chunk.text,
    }

    payload = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=provider.timeout_s) as client:
        res = client.post(endpoint, headers=headers, json=payload)
        res.raise_for_status()
        body = res.json()

    content = body["choices"][0]["message"]["content"]
    parsed = _parse_json_object(content)
    return ChunkStepResponse.model_validate(parsed)


def extract_steps_from_chunks_ai(
    provider: ProviderConfig,
    chunks: list[TranscriptChunk],
) -> list[TutorialStep]:
    steps: list[TutorialStep] = []
    idx = 1
    for chunk in chunks:
        response = _call_reasoning_chunk(provider, chunk)
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
