from pathlib import Path

from video_skill_extractor.chunking import (
    chunk_segments,
    chunk_segments_word_timing,
    read_chunks_jsonl,
    write_chunks_jsonl,
)
from video_skill_extractor.models import TranscriptSegment


def test_chunk_segments_with_overlap() -> None:
    segments = [
        TranscriptSegment(segment_id="1", start_s=0, end_s=30, text="A"),
        TranscriptSegment(segment_id="2", start_s=30, end_s=60, text="B"),
        TranscriptSegment(segment_id="3", start_s=60, end_s=90, text="C"),
        TranscriptSegment(segment_id="4", start_s=90, end_s=120, text="D"),
    ]
    chunks = chunk_segments(segments, window_s=70, overlap_s=20)
    assert len(chunks) >= 2
    assert chunks[0].segment_ids[0] == "1"
    assert chunks[0].text


def test_chunks_jsonl_roundtrip(tmp_path: Path) -> None:
    segments = [TranscriptSegment(segment_id="1", start_s=0, end_s=10, text="Step one")]
    chunks = chunk_segments(segments, window_s=30, overlap_s=5)
    out = tmp_path / "chunks.jsonl"
    write_chunks_jsonl(chunks, out)
    loaded = read_chunks_jsonl(out)
    assert len(loaded) == len(chunks)
    assert loaded[0].chunk_id == chunks[0].chunk_id



def test_chunk_segments_word_timing() -> None:
    segments = [
        TranscriptSegment(
            segment_id="1",
            start_s=0,
            end_s=6,
            text="alpha beta",
            words=[
                {"word": "alpha", "start_s": 0.0, "end_s": 1.0},
                {"word": "beta", "start_s": 1.0, "end_s": 2.0},
            ],
        ),
        TranscriptSegment(
            segment_id="2",
            start_s=6,
            end_s=12,
            text="gamma delta",
            words=[
                {"word": "gamma", "start_s": 6.0, "end_s": 7.0},
                {"word": "delta", "start_s": 7.0, "end_s": 8.0},
            ],
        ),
    ]
    chunks = chunk_segments_word_timing(segments, window_s=5, overlap_s=1)
    assert len(chunks) >= 2
    assert chunks[0].text
