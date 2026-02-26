from __future__ import annotations

import json
from pathlib import Path

from course_step_extractor.models import TranscriptSegment


def parse_whisper_json(path: Path) -> list[TranscriptSegment]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_segments = payload.get("segments", [])
    segments: list[TranscriptSegment] = []
    for idx, item in enumerate(raw_segments, start=1):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                segment_id=str(item.get("id", idx)),
                start_s=float(item.get("start", 0.0)),
                end_s=float(item.get("end", 0.0)),
                text=text,
            )
        )
    return segments


def write_segments_jsonl(segments: list[TranscriptSegment], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [segment.model_dump_json() for segment in segments]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
