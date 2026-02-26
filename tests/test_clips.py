from pathlib import Path

from course_step_extractor.clips import unique_segment_windows, write_clips_jsonl
from course_step_extractor.models import FrameCandidate


def test_unique_segment_windows_merges_rows() -> None:
    rows = [
        FrameCandidate(
            segment_id="1",
            timestamp_s=0.0,
            label="start",
            reason="x",
            confidence=0.8,
            clip_start_s=0.0,
            clip_end_s=2.0,
        ),
        FrameCandidate(
            segment_id="1",
            timestamp_s=1.0,
            label="mid",
            reason="x",
            confidence=0.8,
            clip_start_s=0.5,
            clip_end_s=2.5,
        ),
        FrameCandidate(
            segment_id="2",
            timestamp_s=3.0,
            label="start",
            reason="x",
            confidence=0.8,
            clip_start_s=2.8,
            clip_end_s=4.0,
        ),
    ]
    windows = unique_segment_windows(rows)
    assert windows == [("1", 0.0, 2.5), ("2", 2.8, 4.0)]


def test_write_clips_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "clips.jsonl"
    write_clips_jsonl(
        [
            {
                "segment_id": "1",
                "clip_path": "clips/step_1.mp4",
                "clip_start_s": 0.0,
                "clip_end_s": 2.0,
            }
        ],
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert '"segment_id": "1"' in text
