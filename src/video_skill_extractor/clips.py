from __future__ import annotations

import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

from video_skill_extractor.models import FrameCandidate


def ffmpeg_executable() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def read_frames_jsonl(path: Path) -> list[FrameCandidate]:
    rows: list[FrameCandidate] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(FrameCandidate.model_validate(json.loads(line)))
    return rows


def unique_segment_windows(candidates: list[FrameCandidate]) -> list[tuple[str, float, float]]:
    windows: dict[str, tuple[float, float]] = {}
    for c in candidates:
        current = windows.get(c.segment_id)
        if current is None:
            windows[c.segment_id] = (c.clip_start_s, c.clip_end_s)
            continue
        windows[c.segment_id] = (min(current[0], c.clip_start_s), max(current[1], c.clip_end_s))
    return [(seg_id, start, end) for seg_id, (start, end) in sorted(windows.items())]


def extract_clips(
    video_path: Path,
    candidates: list[FrameCandidate],
    out_dir: Path,
    reencode: bool = True,
) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_executable()

    outputs: list[dict[str, object]] = []
    for segment_id, start_s, end_s in unique_segment_windows(candidates):
        duration = max(0.01, end_s - start_s)
        out_path = out_dir / f"step_{segment_id}.mp4"

        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_s:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration:.3f}",
        ]

        if reencode:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac"]
        else:
            cmd += ["-c", "copy"]

        cmd.append(str(out_path))
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        outputs.append(
            {
                "segment_id": segment_id,
                "clip_path": str(out_path),
                "clip_start_s": start_s,
                "clip_end_s": end_s,
                "duration_s": duration,
            }
        )

    return outputs


def write_clips_jsonl(rows: list[dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row) for row in rows]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
