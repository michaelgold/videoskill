from __future__ import annotations

import json
from pathlib import Path

from video_skill_extractor.models import FrameCandidate, TranscriptSegment

CUE_WORDS = ("now", "next", "then", "add", "switch", "select", "click")


def read_segments_jsonl(path: Path) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        segments.append(TranscriptSegment.model_validate(payload))
    return segments


def plan_frames(
    segments: list[TranscriptSegment],
    clip_pad_s: float = 1.0,
) -> list[FrameCandidate]:
    candidates: list[FrameCandidate] = []
    for i, seg in enumerate(segments):
        duration = max(0.0, seg.end_s - seg.start_s)
        mid = seg.start_s + duration / 2.0

        base_conf = 0.5
        text_lower = seg.text.lower()
        if any(word in text_lower for word in CUE_WORDS):
            base_conf += 0.2

        if i > 0:
            gap = seg.start_s - segments[i - 1].end_s
            if gap >= 1.0:
                base_conf += 0.2

        conf = min(1.0, base_conf)
        clip_start = max(0.0, seg.start_s - clip_pad_s)
        clip_end = seg.end_s + clip_pad_s

        for label, ts in (
            ("start", seg.start_s),
            ("mid", mid),
            ("end", seg.end_s),
        ):
            candidates.append(
                FrameCandidate(
                    segment_id=seg.segment_id,
                    timestamp_s=ts,
                    label=label,
                    reason="segment-window",
                    confidence=conf,
                    clip_start_s=clip_start,
                    clip_end_s=clip_end,
                )
            )
    return candidates


def write_frames_jsonl(candidates: list[FrameCandidate], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [c.model_dump_json() for c in candidates]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
