import json
from pathlib import Path

from course_step_extractor.enrich import (
    enrich_steps,
    plan_sampling_for_step,
    read_frames_manifest_jsonl,
    sample_timestamps,
)
from course_step_extractor.models import TutorialStep
from course_step_extractor.settings import ProviderConfig


def _step(**kwargs) -> TutorialStep:
    base = dict(
        step_id="step_1",
        source_segment_id="1",
        start_s=10.0,
        end_s=20.0,
        clip_start_s=9.0,
        clip_end_s=21.0,
        instruction_text="Rotate the hand to align with the arm.",
        intent="transform_object",
        expected_outcome="Hand aligned",
        confidence=0.8,
    )
    base.update(kwargs)
    return TutorialStep(**base)


def test_plan_sampling_for_motion_step() -> None:
    plan = plan_sampling_for_step(_step())
    assert plan.sample_count >= 4


def test_sample_timestamps_spans_window() -> None:
    ts = sample_timestamps(_step(), 3)
    assert ts[0] == 9.0
    assert ts[-1] == 21.0


def test_enrich_steps_heuristic_mode() -> None:
    rows = enrich_steps([_step()], reasoning=None, vlm=None)
    assert len(rows) == 1
    row = rows[0]
    assert "enrichment" in row
    assert row["enrichment"]["sampling"]["count"] >= 2


def test_read_frames_manifest_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "frames.jsonl"
    p.write_text(
        json.dumps({"step_id": "step_1", "frame_paths": ["a.jpg"]}) + "\n",
        encoding="utf-8",
    )
    by_step = read_frames_manifest_jsonl(p)
    assert by_step["step_1"]["frame_paths"] == ["a.jpg"]


def test_enrich_steps_uses_frame_paths(monkeypatch, tmp_path: Path) -> None:
    def _fake_vlm(provider, step, timestamps, frame_paths, error_rows=None):
        _ = provider, step, timestamps, error_rows
        assert frame_paths == ["x.jpg", "y.jpg"]
        return {
            "motion_detected": True,
            "alignment_ok": True,
            "summary": "ok",
            "confidence": 0.7,
        }

    from course_step_extractor import enrich as mod

    monkeypatch.setattr(mod, "vlm_motion_judge_with_model", _fake_vlm)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    rows = enrich_steps(
        [_step()],
        reasoning=None,
        vlm=cfg,
        frames_by_step={"step_1": {"frame_paths": ["x.jpg", "y.jpg"]}},
    )
    assert rows[0]["enrichment"]["sampling"]["frame_paths"] == ["x.jpg", "y.jpg"]
    assert rows[0]["enrichment"]["vlm_judgement"]["summary"] == "ok"


def test_enrich_steps_orchestrates_finalize(monkeypatch) -> None:
    from course_step_extractor import enrich as mod

    calls = {"final": 0}

    def _fake_vlm(provider, step, timestamps, frame_paths, error_rows=None):
        _ = provider, step, timestamps, frame_paths, error_rows
        return {
            "motion_detected": False,
            "alignment_ok": None,
            "summary": "raw",
            "confidence": 0.1,
        }

    def _fake_final(provider, step, timestamps, raw_judge, error_rows=None):
        _ = provider, step, timestamps, error_rows
        calls["final"] += 1
        assert raw_judge["summary"] == "raw"
        return {
            "motion_detected": True,
            "alignment_ok": True,
            "summary": "final",
            "confidence": 0.9,
        }

    monkeypatch.setattr(mod, "vlm_motion_judge_with_model", _fake_vlm)
    monkeypatch.setattr(mod, "reasoning_finalize_judgement", _fake_final)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="reasoner",
    )
    rows = enrich_steps([_step()], reasoning=cfg, vlm=cfg, orchestrate_with_reasoning=True)
    assert calls["final"] == 1
    assert rows[0]["enrichment"]["vlm_judgement"]["summary"] == "final"



def test_vlm_motion_judge_with_model_success(monkeypatch, tmp_path: Path) -> None:
    from course_step_extractor import enrich as mod

    img = tmp_path / "a.jpg"
    img.write_bytes(b"fake")

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "motion_detected": True,
                                    "alignment_ok": True,
                                    "summary": "seen",
                                    "confidence": 0.8,
                                }
                            )
                        }
                    }
                ]
            }

    class _Client:
        def __init__(self, timeout):
            _ = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers=None, json=None):
            _ = endpoint, headers
            assert json["messages"][1]["content"][1]["type"] == "image_url"
            return _Resp()

    monkeypatch.setattr(mod.httpx, "Client", _Client)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    out = mod.vlm_motion_judge_with_model(
        cfg,
        _step(),
        [1.0, 2.0],
        [str(img)],
        error_rows=[],
    )
    assert out["motion_detected"] is True
    assert out["summary"] == "seen"


def test_vlm_motion_judge_with_model_error_path(monkeypatch) -> None:
    from course_step_extractor import enrich as mod

    class _Client:
        def __init__(self, timeout):
            _ = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, endpoint, headers=None, json=None):
            _ = endpoint, headers, json
            raise RuntimeError("boom")

    monkeypatch.setattr(mod.httpx, "Client", _Client)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    errors = []
    out = mod.vlm_motion_judge_with_model(
        cfg,
        _step(),
        [1.0],
        ["/does/not/exist.jpg"],
        error_rows=errors,
    )
    assert out["summary"] == "vlm_unavailable_or_parse_error"
    assert any(e["kind"] in {"frame_read_error", "model_parse_or_call_error"} for e in errors)
