import json
from pathlib import Path

from video_skill_extractor.transcript import parse_whisper_json, write_segments_jsonl


def test_parse_whisper_json_and_write_jsonl(tmp_path: Path) -> None:
    src = tmp_path / "whisper.json"
    payload = {
        "segments": [
            {"id": 0, "start": 0.0, "end": 1.2, "text": " Hello world "},
            {"id": 1, "start": 1.2, "end": 2.0, "text": ""},
            {"id": 2, "start": 2.0, "end": 3.4, "text": "Next step"},
        ]
    }
    src.write_text(json.dumps(payload), encoding="utf-8")

    segments = parse_whisper_json(src)
    assert len(segments) == 2
    assert segments[0].text == "Hello world"

    out = tmp_path / "segments.jsonl"
    write_segments_jsonl(segments, out)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert "Hello world" in lines[0]
