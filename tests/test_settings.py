import json
from pathlib import Path

from video_skill_extractor.settings import AppConfig, validate_config


def _valid_payload() -> dict:
    provider = {
        "provider": "openai-compatible",
        "base_url": "http://192.168.1.10:8000",
        "model": "test-model",
        "api_key_env": None,
        "timeout_s": 10.0,
    }
    return {
        "transcription": provider,
        "reasoning": provider,
        "vlm": provider,
    }


def test_validate_config_ok(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    ok, msg = validate_config(path)
    assert ok is True
    assert msg == "OK"

    cfg = AppConfig.load(path)
    assert cfg.vlm.model == "test-model"


def test_validate_config_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    ok, msg = validate_config(path)
    assert ok is False
    assert "not found" in msg


def test_validate_config_bad_json(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not-json}", encoding="utf-8")

    ok, msg = validate_config(path)
    assert ok is False
    assert "Invalid JSON" in msg


def test_validate_config_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = _valid_payload()
    payload["reasoning"] = {"provider": "x", "base_url": "http://127.0.0.1:8000"}
    path.write_text(json.dumps(payload), encoding="utf-8")

    ok, msg = validate_config(path)
    assert ok is False
    assert "Validation error" in msg
