from pathlib import Path

from course_step_extractor.frame_plan import plan_frames, read_segments_jsonl, write_frames_jsonl
from course_step_extractor.models import TranscriptSegment


def test_plan_frames_generates_start_mid_end_with_clip_windows() -> None:
    segments = [
        TranscriptSegment(segment_id="1", start_s=0.0, end_s=2.0, text="now add cube"),
        TranscriptSegment(segment_id="2", start_s=3.5, end_s=5.0, text="scale it"),
    ]
    candidates = plan_frames(segments, clip_pad_s=1.0)
    assert len(candidates) == 6
    first = candidates[0]
    assert first.segment_id == "1"
    assert first.label == "start"
    assert first.clip_start_s == 0.0
    assert first.clip_end_s == 3.0


def test_read_write_frames_jsonl_roundtrip(tmp_path: Path) -> None:
    segments_path = tmp_path / "segments.jsonl"
    segments_path.write_text(
        "\n".join(
            [
                '{"segment_id":"1","start_s":0.0,"end_s":1.0,"text":"next step"}',
                '{"segment_id":"2","start_s":1.0,"end_s":2.5,"text":"click tool"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    segments = read_segments_jsonl(segments_path)
    candidates = plan_frames(segments)
    out_path = tmp_path / "frames.jsonl"
    write_frames_jsonl(candidates, out_path)
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6
    assert '"segment_id":"1"' in lines[0]
