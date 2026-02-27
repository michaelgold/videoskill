from pathlib import Path

from course_step_extractor.chunking import chunk_segments, read_chunks_jsonl, write_chunks_jsonl
from course_step_extractor.models import TranscriptSegment


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
