import json
from pathlib import Path

from typer.testing import CliRunner

import course_step_extractor.cli as cli
from course_step_extractor.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def _config_file(tmp_path: Path) -> Path:
    provider = {
        "provider": "openai-compatible",
        "base_url": "http://127.0.0.1:8080",
        "model": "test-model",
        "api_key_env": None,
        "timeout_s": 10.0,
    }
    payload = {
        "transcription": provider,
        "reasoning": provider,
        "vlm": provider,
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sample_command_outputs_markdown() -> None:
    result = runner.invoke(app, ["sample"])
    assert result.exit_code == 0
    assert "## Open video" in result.stdout


def test_config_validate_command(tmp_path: Path) -> None:
    path = _config_file(tmp_path)
    result = runner.invoke(app, ["config-validate", "--config", str(path)])
    assert result.exit_code == 0
    assert "OK:" in result.stdout


def test_config_validate_command_bad_path() -> None:
    result = runner.invoke(app, ["config-validate", "--config", "missing.json"])
    assert result.exit_code == 1


def test_providers_ping_command(monkeypatch, tmp_path: Path) -> None:
    path = _config_file(tmp_path)

    def _fake_ping(_provider, path: str = "/"):
        return {"ok": True, "status_code": 200, "url": f"http://example.test{path}"}

    monkeypatch.setattr(cli, "ping_provider", _fake_ping)
    result = runner.invoke(app, ["providers-ping", "--config", str(path), "--path", "/v1/models"])
    assert result.exit_code == 0
    assert "transcription: ok" in result.stdout
    assert "reasoning: ok" in result.stdout
    assert "vlm: ok" in result.stdout


def test_providers_ping_command_fails(monkeypatch, tmp_path: Path) -> None:
    path = _config_file(tmp_path)

    def _fake_ping(_provider, path: str = "/"):
        return {"ok": False, "status_code": 503, "url": f"http://example.test{path}"}

    monkeypatch.setattr(cli, "ping_provider", _fake_ping)
    result = runner.invoke(app, ["providers-ping", "--config", str(path)])
    assert result.exit_code == 1


def test_transcript_parse_command(tmp_path: Path) -> None:
    src = tmp_path / "whisper.json"
    src.write_text(
        json.dumps({"segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "hello"}]}),
        encoding="utf-8",
    )
    out = tmp_path / "segments.jsonl"
    result = runner.invoke(app, ["transcript-parse", "--input", str(src), "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "parsed_segments=1" in result.stdout


def test_frames_plan_command(tmp_path: Path) -> None:
    segments = tmp_path / "segments.jsonl"
    segments.write_text(
        '{"segment_id":"1","start_s":0.0,"end_s":1.0,"text":"now click"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "frames.jsonl"
    result = runner.invoke(
        app,
        ["frames-plan", "--segments", str(segments), "--out", str(out), "--clip-pad-s", "0.5"],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "frame_candidates=3" in result.stdout
