from pathlib import Path

from video_skill_extractor.frames import (
    extract_frames_for_steps,
    read_steps_jsonl,
    write_frames_manifest_jsonl,
)


def test_read_steps_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "steps.jsonl"
    p.write_text(
        '{"step_id":"step_1","source_segment_id":"1","start_s":0.0,"end_s":1.0,'
        '"clip_start_s":0.0,"clip_end_s":1.2,"instruction_text":"rotate hand",'
        '"intent":"transform_object","expected_outcome":"aligned","confidence":0.8}\n',
        encoding="utf-8",
    )
    rows = read_steps_jsonl(p)
    assert rows[0].step_id == "step_1"


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


def test_extract_frames_for_steps(monkeypatch, tmp_path: Path) -> None:
    from video_skill_extractor import frames as mod

    created = []

    def _fake_run(cmd, check, capture_output, text):
        _ = check, capture_output, text
        if cmd and cmd[0] == "ffprobe":
            class _R:
                stdout = "2.0\n"

            return _R()

        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"jpg")
        created.append(out)

        class _R:
            stdout = ""

        return _R()

    monkeypatch.setattr(mod, "ffmpeg_executable", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    from video_skill_extractor.models import TutorialStep

    rows = extract_frames_for_steps(
        video_path=tmp_path / "v.mp4",
        steps=[
            TutorialStep(
                step_id="step_1",
                source_segment_id="1",
                start_s=0.0,
                end_s=1.0,
                clip_start_s=0.0,
                clip_end_s=2.0,
                instruction_text="a",
                intent="b",
                expected_outcome="c",
                confidence=0.5,
            )
        ],
        out_dir=tmp_path / "frames",
        sample_count=2,
    )
    assert len(rows) == 1
    assert len(rows[0]["frame_paths"]) == 2
    assert all(Path(p).exists() for p in rows[0]["frame_paths"])
    assert len(created) == 2
