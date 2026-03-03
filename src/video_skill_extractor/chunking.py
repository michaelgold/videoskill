from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from video_skill_extractor.models import TranscriptSegment


class TranscriptChunk(BaseModel):
    chunk_id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    segment_ids: list[str] = Field(default_factory=list)
    text: str = Field(min_length=1)


def chunk_segments(
    segments: list[TranscriptSegment],
    window_s: float = 120.0,
    overlap_s: float = 15.0,
) -> list[TranscriptChunk]:
    if not segments:
        return []

    chunks: list[TranscriptChunk] = []
    i = 0
    chunk_idx = 1
    n = len(segments)
    while i < n:
        start = segments[i].start_s
        end_limit = start + window_s
        j = i
        while j < n and segments[j].end_s <= end_limit:
            j += 1
        if j == i:
            j += 1

        selected = segments[i:j]
        text = " ".join(s.text.strip() for s in selected if s.text.strip()).strip()
        if text:
            chunks.append(
                TranscriptChunk(
                    chunk_id=f"chunk_{chunk_idx}",
                    start_s=selected[0].start_s,
                    end_s=selected[-1].end_s,
                    segment_ids=[s.segment_id for s in selected],
                    text=text,
                )
            )
            chunk_idx += 1

        if j >= n:
            break

        next_start_target = selected[-1].end_s - overlap_s
        k = i
        while k < n and segments[k].start_s < next_start_target:
            k += 1
        i = max(i + 1, k)

    return chunks


def write_chunks_jsonl(chunks: list[TranscriptChunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [c.model_dump_json() for c in chunks]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_chunks_jsonl(path: Path) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        chunks.append(TranscriptChunk.model_validate(json.loads(line)))
    return chunks


def chunk_segments_word_timing(
    segments: list[TranscriptSegment],
    window_s: float = 120.0,
    overlap_s: float = 15.0,
) -> list[TranscriptChunk]:
    # Build sentence-like units from timed words using punctuation boundaries.
    # This preserves semantic action boundaries better than raw word windows.
    units: list[tuple[str, float, float, list[str]]] = []
    for seg in segments:
        if not seg.words:
            continue
        current_words: list[str] = []
        unit_start: float | None = None
        unit_end: float | None = None
        unit_seg_ids: list[str] = []

        for w in seg.words:
            token = w.word.strip()
            if not token:
                continue
            if unit_start is None:
                unit_start = w.start_s
                unit_seg_ids = [seg.segment_id]
            unit_end = w.end_s
            current_words.append(token)

            is_boundary = token.endswith((".", "!", "?", ",", ";", ":", "—", "--"))
            if is_boundary:
                text = " ".join(current_words).strip()
                if text and unit_start is not None and unit_end is not None:
                    units.append((text, unit_start, unit_end, unit_seg_ids.copy()))
                current_words = []
                unit_start = None
                unit_end = None
                unit_seg_ids = []

        if current_words and unit_start is not None and unit_end is not None:
            text = " ".join(current_words).strip()
            units.append((text, unit_start, unit_end, [seg.segment_id]))

    if not units:
        # strict mode: no word timings available
        return []

    chunks: list[TranscriptChunk] = []
    i = 0
    chunk_idx = 1
    n = len(units)
    while i < n:
        start = units[i][1]
        end_limit = start + window_s
        j = i
        while j < n and units[j][2] <= end_limit:
            j += 1
        if j == i:
            j += 1

        selected = units[i:j]
        text = " ".join(u[0] for u in selected).strip()
        seg_ids: list[str] = []
        seen = set()
        for _, _, _, sids in selected:
            for sid in sids:
                if sid not in seen:
                    seen.add(sid)
                    seg_ids.append(sid)

        chunks.append(
            TranscriptChunk(
                chunk_id=f"chunk_{chunk_idx}",
                start_s=selected[0][1],
                end_s=selected[-1][2],
                segment_ids=seg_ids,
                text=text,
            )
        )
        chunk_idx += 1

        if j >= n:
            break

        next_start_target = selected[-1][2] - overlap_s
        k = i
        while k < n and units[k][1] < next_start_target:
            k += 1
        i = max(i + 1, k)

    return chunks
