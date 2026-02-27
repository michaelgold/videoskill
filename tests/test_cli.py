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


def test_transcribe_command(monkeypatch, tmp_path: Path) -> None:
    cfg_path = _config_file(tmp_path)
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"vid")
    out = tmp_path / "whisper.json"

    def _fake_transcribe(provider, video_path, out_path):
        _ = provider, video_path
        payload = {"segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "hello"}]}
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(cli, "transcribe_video_whisper_openai", _fake_transcribe)
    result = runner.invoke(
        app,
        [
            "transcribe",
            "--video",
            str(video),
            "--out",
            str(out),
            "--config",
            str(cfg_path),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "transcribed_segments=1" in result.stdout


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


def test_transcript_chunk_command(tmp_path: Path) -> None:
    segments = tmp_path / "segments.jsonl"
    segments.write_text(
        "\n".join(
            [
                '{"segment_id":"1","start_s":0.0,"end_s":20.0,"text":"a"}',
                '{"segment_id":"2","start_s":20.0,"end_s":40.0,"text":"b"}',
                '{"segment_id":"3","start_s":40.0,"end_s":60.0,"text":"c"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "chunks.jsonl"
    result = runner.invoke(
        app,
        [
            "transcript-chunk",
            "--segments",
            str(segments),
            "--out",
            str(out),
            "--window-s",
            "40",
            "--overlap-s",
            "10",
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "chunks=" in result.stdout


def test_steps_extract_command_ai_mode_with_errors(monkeypatch, tmp_path: Path) -> None:
    segments = tmp_path / "segments.jsonl"
    segments.write_text(
        '{"segment_id":"1","start_s":0.0,"end_s":1.0,"text":"now click"}\n',
        encoding="utf-8",
    )
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(
        '{"chunk_id":"chunk_1","start_s":0.0,"end_s":5.0,"segment_ids":["1"],"text":"now click"}\n',
        encoding="utf-8",
    )
    clips = tmp_path / "clips.jsonl"
    clips.write_text('{"segment_id":"1","clip_path":"clips/step_1.mp4"}\n', encoding="utf-8")
    out = tmp_path / "steps_ai.jsonl"

    def _fake_extract_steps_ai(_provider, _chunks, error_rows=None):
        from course_step_extractor.models import TutorialStep

        if error_rows is not None:
            error_rows.append({"kind": "fake_error", "chunk_id": "chunk_1"})
        return [
            TutorialStep(
                step_id="step_1",
                source_segment_id="1",
                start_s=0.0,
                end_s=1.0,
                clip_start_s=0.0,
                clip_end_s=1.2,
                instruction_text="Click the button",
                intent="Demonstrate selection",
                expected_outcome="Selection changes",
                confidence=0.8,
            )
        ]

    monkeypatch.setattr(cli, "extract_steps_from_chunks_ai", _fake_extract_steps_ai)
    cfg_path = _config_file(tmp_path)
    result = runner.invoke(
        app,
        [
            "steps-extract",
            "--segments",
            str(segments),
            "--clips-manifest",
            str(clips),
            "--chunks",
            str(chunks),
            "--mode",
            "ai",
            "--config",
            str(cfg_path),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "mode=ai" in result.stdout
    assert "parse_errors=1" in result.stdout
    assert Path(str(out) + ".errors.jsonl").exists()


def test_steps_extract_command_ai_mode(monkeypatch, tmp_path: Path) -> None:
    segments = tmp_path / "segments.jsonl"
    segments.write_text(
        '{"segment_id":"1","start_s":0.0,"end_s":1.0,"text":"now click"}\n',
        encoding="utf-8",
    )
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(
        '{"chunk_id":"chunk_1","start_s":0.0,"end_s":5.0,"segment_ids":["1"],"text":"now click"}\n',
        encoding="utf-8",
    )
    clips = tmp_path / "clips.jsonl"
    clips.write_text('{"segment_id":"1","clip_path":"clips/step_1.mp4"}\n', encoding="utf-8")
    out = tmp_path / "steps_ai.jsonl"

    def _fake_extract_steps_ai(_provider, _chunks):
        from course_step_extractor.models import TutorialStep

        return [
            TutorialStep(
                step_id="step_1",
                source_segment_id="1",
                start_s=0.0,
                end_s=1.0,
                clip_start_s=0.0,
                clip_end_s=1.2,
                instruction_text="Click the button",
                intent="Demonstrate selection",
                expected_outcome="Selection changes",
                confidence=0.8,
            )
        ]

    monkeypatch.setattr(cli, "extract_steps_from_chunks_ai", _fake_extract_steps_ai)
    cfg_path = _config_file(tmp_path)
    result = runner.invoke(
        app,
        [
            "steps-extract",
            "--segments",
            str(segments),
            "--clips-manifest",
            str(clips),
            "--chunks",
            str(chunks),
            "--mode",
            "ai",
            "--config",
            str(cfg_path),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "mode=ai" in result.stdout


def test_steps_enrich_command_ai_with_errors(monkeypatch, tmp_path: Path) -> None:
    steps = tmp_path / "steps.jsonl"
    steps.write_text(
        '{"step_id":"step_1","source_segment_id":"1","start_s":0.0,"end_s":1.0,'
        '"clip_start_s":0.0,"clip_end_s":1.2,"instruction_text":"rotate hand",'
        '"intent":"transform_object","expected_outcome":"aligned","confidence":0.8}\n',
        encoding="utf-8",
    )
    out = tmp_path / "steps.enriched.ai.jsonl"
    cfg_path = _config_file(tmp_path)

    def _fake_enrich(steps, reasoning=None, vlm=None, error_rows=None):
        _ = steps, reasoning, vlm
        if error_rows is not None:
            error_rows.append({"kind": "fake_error", "step_id": "step_1"})
        return [
            {
                "step_id": "step_1",
                "source_segment_id": "1",
                "start_s": 0.0,
                "end_s": 1.0,
                "clip_start_s": 0.0,
                "clip_end_s": 1.2,
                "instruction_text": "rotate hand",
                "intent": "transform_object",
                "expected_outcome": "aligned",
                "confidence": 0.8,
                "enrichment": {"sampling": {"count": 3}, "vlm_judgement": {}},
            }
        ]

    monkeypatch.setattr(cli, "enrich_steps", _fake_enrich)
    result = runner.invoke(
        app,
        [
            "steps-enrich",
            "--steps",
            str(steps),
            "--out",
            str(out),
            "--mode",
            "ai",
            "--config",
            str(cfg_path),
        ],
    )
    assert result.exit_code == 0
    assert "parse_errors=1" in result.stdout
    assert Path(str(out) + ".errors.jsonl").exists()


def test_steps_enrich_command_heuristic(tmp_path: Path) -> None:
    steps = tmp_path / "steps.jsonl"
    steps.write_text(
        '{"step_id":"step_1","source_segment_id":"1","start_s":0.0,"end_s":1.0,'
        '"clip_start_s":0.0,"clip_end_s":1.2,"instruction_text":"rotate hand",'
        '"intent":"transform_object","expected_outcome":"aligned","confidence":0.8}\n',
        encoding="utf-8",
    )
    out = tmp_path / "steps.enriched.jsonl"
    result = runner.invoke(app, ["steps-enrich", "--steps", str(steps), "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "enriched_steps=1" in result.stdout


def test_steps_extract_command(monkeypatch, tmp_path: Path) -> None:
    segments = tmp_path / "segments.jsonl"
    segments.write_text(
        '{"segment_id":"1","start_s":0.0,"end_s":1.0,"text":"now click"}\n',
        encoding="utf-8",
    )
    clips = tmp_path / "clips.jsonl"
    clips.write_text('{"segment_id":"1","clip_path":"clips/step_1.mp4"}\n', encoding="utf-8")
    out = tmp_path / "steps.jsonl"

    def _fake_extract_steps(parsed_segments, clips_by_segment):
        _ = parsed_segments, clips_by_segment
        from course_step_extractor.models import TutorialStep

        return [
            TutorialStep(
                step_id="step_1",
                source_segment_id="1",
                start_s=0.0,
                end_s=1.0,
                clip_start_s=0.0,
                clip_end_s=1.2,
                instruction_text="Click the button",
                intent="Demonstrate selection",
                expected_outcome="Selection changes",
                confidence=0.8,
            )
        ]

    monkeypatch.setattr(cli, "extract_steps", _fake_extract_steps)
    result = runner.invoke(
        app,
        [
            "steps-extract",
            "--segments",
            str(segments),
            "--clips-manifest",
            str(clips),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "steps=1" in result.stdout


def test_markdown_render_command(tmp_path: Path) -> None:
    steps = tmp_path / "steps.jsonl"
    steps.write_text(
        '{"step_id":"step_1","instruction_text":"Add cube","intent":"Create","expected_outcome":"Cube","start_s":0.0,"end_s":1.0,"clip_start_s":0.0,"clip_end_s":1.2,"confidence":0.8}\n',
        encoding="utf-8",
    )
    out = tmp_path / "lesson.md"
    result = runner.invoke(app, ["markdown-render", "--steps", str(steps), "--out", str(out), "--title", "Lesson 1"])
    assert result.exit_code == 0
    assert out.exists()
    assert "markdown_steps=1" in result.stdout


def test_clips_extract_command(monkeypatch, tmp_path: Path) -> None:
    frames = tmp_path / "frames.jsonl"
    frames.write_text(
        '{"segment_id":"1","timestamp_s":0.0,"label":"start","reason":"x","confidence":0.9,"clip_start_s":0.0,"clip_end_s":1.2}\n',
        encoding="utf-8",
    )
    out_dir = tmp_path / "clips"
    manifest = tmp_path / "clips.jsonl"

    def _fake_extract(_video, _candidates, out_dir, reencode=True):
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "step_1.mp4"
        p.write_bytes(b"fake")
        return [
            {
                "segment_id": "1",
                "clip_path": str(p),
                "clip_start_s": 0.0,
                "clip_end_s": 1.2,
                "duration_s": 1.2,
            }
        ]

    monkeypatch.setattr(cli, "extract_clips", _fake_extract)

    video = tmp_path / "video.mp4"
    video.write_bytes(b"vid")
    result = runner.invoke(
        app,
        [
            "clips-extract",
            "--video",
            str(video),
            "--frames",
            str(frames),
            "--out-dir",
            str(out_dir),
            "--manifest-out",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    assert manifest.exists()
    assert "clips=1" in result.stdout
