from pathlib import Path

from course_step_extractor.frames import write_frames_manifest_jsonl


def test_write_frames_manifest_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "frames_manifest.jsonl"
    rows = [
        {
            "step_id": "step_1",
            "source_segment_id": "1",
            "frame_paths": ["frames/step_1/frame_01.jpg"],
            "frame_timestamps": [1.23],
        }
    ]
    write_frames_manifest_jsonl(rows, out)
    text = out.read_text(encoding="utf-8")
    assert '"step_id": "step_1"' in text
