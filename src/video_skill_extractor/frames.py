from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

from video_skill_extractor.models import TutorialStep


def ffmpeg_executable() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def read_steps_jsonl(path: Path) -> list[TutorialStep]:
    rows: list[TutorialStep] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(TutorialStep.model_validate(json.loads(line)))
    return rows


def _sample_timestamps(step: TutorialStep, sample_count: int = 3) -> list[float]:
    start = step.clip_start_s
    end = step.clip_end_s
    if sample_count <= 1 or end <= start:
        return [round(start, 3)]
    span = end - start
    return [round(start + span * (i / (sample_count - 1)), 3) for i in range(sample_count)]


def _video_duration_s(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(res.stdout.strip())


def extract_frames_for_steps(
    video_path: Path,
    steps: list[TutorialStep],
    out_dir: Path,
    sample_count: int = 3,
) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_executable()
    duration_s = _video_duration_s(video_path)

    rows: list[dict[str, object]] = []
    for step in steps:
        step_dir = out_dir / step.step_id
        step_dir.mkdir(parents=True, exist_ok=True)

        frame_paths: list[str] = []
        sampled = _sample_timestamps(step, sample_count=sample_count)
        for idx, ts in enumerate(sampled, start=1):
            ts = max(0.0, min(ts, max(0.0, duration_s - 0.5)))
            out_path = step_dir / f"frame_{idx:02d}_{ts:.3f}.jpg"
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(out_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            frame_paths.append(str(out_path))

        rows.append(
            {
                "step_id": step.step_id,
                "source_segment_id": step.source_segment_id,
                "frame_paths": frame_paths,
                "frame_timestamps": sampled,
            }
        )

    return rows


def write_frames_manifest_jsonl(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
