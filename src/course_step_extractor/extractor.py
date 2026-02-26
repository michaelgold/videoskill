from __future__ import annotations

import json
import re
from pathlib import Path

from course_step_extractor.models import TranscriptSegment, TutorialStep


def read_clips_manifest_jsonl(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        seg_id = str(payload.get("segment_id", ""))
        if not seg_id:
            continue
        rows[seg_id] = payload
    return rows


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0].strip()
    return sentence if sentence else text.strip()


def extract_single_step(
    segment: TranscriptSegment,
    clip_row: dict[str, object] | None,
) -> TutorialStep:
    instruction = _first_sentence(segment.text)
    if not instruction:
        instruction = "Review transcript segment"

    outcome = "Action reflected in timeline segment"
    if clip_row and clip_row.get("clip_path"):
        outcome = f"Action visible in clip {clip_row['clip_path']}"

    return TutorialStep(
        step_id=f"step_{segment.segment_id}",
        instruction_text=instruction,
        intent="Replicate demonstrated tutorial action",
        expected_outcome=outcome,
        confidence=0.6,
    )


def extract_steps(
    segments: list[TranscriptSegment],
    clips_by_segment: dict[str, dict[str, object]],
) -> list[TutorialStep]:
    steps: list[TutorialStep] = []
    for segment in segments:
        clip_row = clips_by_segment.get(segment.segment_id)
        steps.append(extract_single_step(segment, clip_row))
    return steps


def write_steps_jsonl(steps: list[TutorialStep], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [step.model_dump_json() for step in steps]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
