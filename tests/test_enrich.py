import json
from pathlib import Path

from video_skill_extractor.enrich import (
    enrich_steps,
    plan_sampling_for_step,
    read_frames_manifest_jsonl,
    sample_timestamps,
)
from video_skill_extractor.models import TutorialStep
from video_skill_extractor.settings import ProviderConfig


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

    from video_skill_extractor import enrich as mod

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
    from video_skill_extractor import enrich as mod

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
    from video_skill_extractor import enrich as mod

    img = tmp_path / "a.jpg"
    img.write_bytes(b"fake")

    def _fake_chat(*args, **kwargs):
        _ = args, kwargs
        return {
            "motion_detected": True,
            "alignment_ok": True,
            "summary": "seen",
            "confidence": 0.8,
        }

    monkeypatch.setattr(mod, "_chat_with_images", _fake_chat)
    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    out = mod.vlm_motion_judge_with_model(cfg, _step(), [1.0, 2.0], [str(img)], error_rows=[])
    assert out["motion_detected"] is True
    assert out["summary"] == "seen"


def test_vlm_motion_judge_with_model_error_path(monkeypatch) -> None:
    from video_skill_extractor import enrich as mod

    monkeypatch.setattr(mod, "_chat_with_images", lambda *a, **k: None)
    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    out = mod.vlm_motion_judge_with_model(
        cfg,
        _step(),
        [1.0],
        ["/does/not/exist.jpg"],
        error_rows=[],
    )
    assert out["summary"] == "vlm_unavailable_or_parse_error"


def test_vlm_select_frames_with_model(monkeypatch) -> None:
    from video_skill_extractor import enrich as mod

    def _fake_chat(provider, system, payload_context, frame_paths, output_model, **kwargs):
        _ = provider, system, payload_context, output_model, kwargs
        assert len(frame_paths) == 3
        return {"selected_indices": [0, 2], "rationale": "best evidence"}

    monkeypatch.setattr(mod, "_chat_with_images", _fake_chat)
    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    out = mod.vlm_select_frames_with_model(cfg, _step(), [1.0], ["a.jpg", "b.jpg", "c.jpg"])
    assert out["selected_indices"] == [0, 2]


def test_vlm_signal_pass_with_model(monkeypatch) -> None:
    from video_skill_extractor import enrich as mod

    def _fake_chat(provider, system, payload_context, frame_paths, output_model, **kwargs):
        _ = provider, system, payload_context, output_model, kwargs
        assert frame_paths == ["b.jpg"]
        return {
            "summary": "clear rotation",
            "detected_events": ["rotate"],
            "observations": ["wrist angle changed"],
            "before_observations": ["hand neutral"],
            "after_observations": ["hand rotated"],
            "changes_detected": ["wrist rotation"],
            "unchanged_signals": ["camera angle"],
            "change_confidence": 0.77,
            "confidence": 0.8,
        }

    monkeypatch.setattr(mod, "_chat_with_images", _fake_chat)
    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8081",
        model="vlm",
    )
    out = mod.vlm_signal_pass_with_model(
        cfg,
        _step(),
        selected_indices=[1],
        frame_paths=["a.jpg", "b.jpg"],
    )
    assert out["summary"] == "clear rotation"
    assert out["changes_detected"] == ["wrist rotation"]


def test_enrich_steps_two_pass_in_ai_mode(monkeypatch) -> None:
    from video_skill_extractor import enrich as mod

    def _fake_vlm(provider, step, timestamps, frame_paths, error_rows=None):
        _ = provider, step, timestamps, frame_paths, error_rows
        return {
            "motion_detected": True,
            "alignment_ok": True,
            "summary": "raw",
            "confidence": 0.3,
        }

    def _fake_select(provider, step, timestamps, frame_paths, error_rows=None):
        _ = provider, step, timestamps, frame_paths, error_rows
        return {"selected_indices": [0], "rationale": "front frame"}

    def _fake_signal(provider, step, selected_indices, frame_paths, error_rows=None):
        _ = provider, step, selected_indices, frame_paths, error_rows
        return {
            "summary": "signal summary",
            "detected_events": ["mode_switch", "drop_image"],
            "observations": ["object mode visible"],
            "before_observations": ["no image in viewport"],
            "after_observations": ["reference image in viewport"],
            "changes_detected": ["image added to viewport"],
            "unchanged_signals": ["grid still visible"],
            "change_confidence": 0.91,
            "confidence": 0.88,
        }

    monkeypatch.setattr(mod, "vlm_motion_judge_with_model", _fake_vlm)
    monkeypatch.setattr(mod, "vlm_select_frames_with_model", _fake_select)
    monkeypatch.setattr(mod, "vlm_signal_pass_with_model", _fake_signal)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="reasoner",
    )
    rows = enrich_steps(
        [_step()],
        reasoning=cfg,
        vlm=cfg,
        orchestrate_with_reasoning=True,
        frames_by_step={"step_1": {"frame_paths": ["f1.jpg", "f2.jpg"]}},
    )
    e = rows[0]["enrichment"]
    assert e["frame_selection"]["selected_indices"] == [0]
    assert e["signal_pass"]["summary"] == "signal summary"
    assert e["vlm_judgement"]["summary"] == "signal summary"
    assert e["vlm_judgement"]["changes_detected"] == ["image added to viewport"]
