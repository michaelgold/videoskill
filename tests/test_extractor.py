from pathlib import Path

from video_skill_extractor.extractor import (
    extract_single_step,
    extract_steps,
    read_clips_manifest_jsonl,
    write_steps_jsonl,
)
from video_skill_extractor.models import TranscriptSegment


def test_read_clips_manifest_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "clips.jsonl"
    path.write_text(
        '{"segment_id":"1","clip_path":"clips/step_1.mp4"}\n'
        '{"segment_id":"2","clip_path":"clips/step_2.mp4"}\n',
        encoding="utf-8",
    )
    rows = read_clips_manifest_jsonl(path)
    assert rows["1"]["clip_path"] == "clips/step_1.mp4"


def test_extract_single_step_uses_clip_path() -> None:
    seg = TranscriptSegment(segment_id="1", start_s=0.0, end_s=1.0, text="Now add a cube.")
    step = extract_single_step(seg, {"clip_path": "clips/step_1.mp4"})
    assert step.step_id == "step_1"
    assert "Now add a cube" in step.instruction_text
    assert "clips/step_1.mp4" in step.expected_outcome


def test_extract_steps_and_write_jsonl(tmp_path: Path) -> None:
    segs = [
        TranscriptSegment(segment_id="1", start_s=0.0, end_s=1.0, text="Select mesh"),
        TranscriptSegment(segment_id="2", start_s=1.0, end_s=2.0, text="Scale it up"),
    ]
    clips = {"1": {"clip_path": "clips/step_1.mp4"}}
    steps = extract_steps(segs, clips)
    assert len(steps) == 2

    out = tmp_path / "steps.jsonl"
    write_steps_jsonl(steps, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert '"step_id":"step_1"' in lines[0]
