from pathlib import Path

from video_skill_extractor.clips import (
    extract_clips,
    read_frames_jsonl,
    unique_segment_windows,
    write_clips_jsonl,
)
from video_skill_extractor.models import FrameCandidate


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


def test_read_frames_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "frames.jsonl"
    p.write_text(
        '{"segment_id":"1","timestamp_s":0.5,"label":"mid","reason":"x",'
        '"confidence":0.9,"clip_start_s":0.0,"clip_end_s":2.0}\n',
        encoding="utf-8",
    )
    rows = read_frames_jsonl(p)
    assert len(rows) == 1
    assert rows[0].segment_id == "1"


def test_extract_clips_reencode_and_copy(monkeypatch, tmp_path: Path) -> None:
    from video_skill_extractor import clips as mod

    calls: list[list[str]] = []

    def _fake_run(cmd, check, capture_output, text):
        _ = check, capture_output, text
        calls.append(cmd)
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")

    monkeypatch.setattr(mod, "ffmpeg_executable", lambda: "/usr/bin/ffmpeg")
    monkeypatch.setattr(mod.subprocess, "run", _fake_run)

    cands = [
        FrameCandidate(
            segment_id="1",
            timestamp_s=0.0,
            label="start",
            reason="x",
            confidence=0.8,
            clip_start_s=0.0,
            clip_end_s=2.0,
        )
    ]

    out_rows = extract_clips(tmp_path / "v.mp4", cands, tmp_path / "clips", reencode=True)
    assert out_rows[0]["segment_id"] == "1"
    assert any("libx264" in part for part in calls[0])

    out_rows_copy = extract_clips(tmp_path / "v.mp4", cands, tmp_path / "clips2", reencode=False)
    assert out_rows_copy[0]["duration_s"] == 2.0
    assert "copy" in calls[1]


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
