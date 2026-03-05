from video_skill_extractor.models import TranscriptSegment
from video_skill_extractor.postprocess import align_steps_with_transcript, normalize_steps


def test_normalize_steps_cleans_signal_and_dedupes() -> None:
    rows = [
        {
            "step_id": "step_1",
            "start_s": 0.0,
            "end_s": 5.0,
            "clip_end_s": 5.0,
            "instruction_text": "Open menu",
            "enrichment": {
                "vlm_judgement": {"summary": "no evidence detected", "confidence": 0.9},
                "signal_pass": {
                    "changes_detected": ["Yes", "menu opened"],
                    "detected_events": ["none", "click"],
                },
            },
        },
        {
            "step_id": "step_2",
            "start_s": 5.5,
            "end_s": 8.0,
            "clip_end_s": 8.0,
            "instruction_text": "open menu",
            "enrichment": {"vlm_judgement": {"summary": "ok", "confidence": 0.8}},
        },
    ]
    out = normalize_steps(rows)
    assert len(out) == 1
    sig = out[0]["enrichment"]["signal_pass"]
    assert sig["changes_detected"] == ["menu opened"]
    assert out[0]["enrichment"]["vlm_judgement"]["confidence"] <= 0.35


def test_align_steps_with_transcript_adds_support() -> None:
    rows = [{"step_id": "step_1", "start_s": 1.0, "end_s": 4.0, "instruction_text": "Do x"}]
    segments = [
        TranscriptSegment(segment_id="1", start_s=0.0, end_s=2.0, text="Intro"),
        TranscriptSegment(segment_id="2", start_s=2.0, end_s=5.0, text="Do x now"),
    ]
    out = align_steps_with_transcript(rows, segments)
    ts = out[0]["transcript_support"]
    assert ts["segment_ids"] == ["1", "2"]
    assert ts["quoted_snippets"]
    assert 0.0 <= ts["alignment_confidence"] <= 1.0


def test_calibrate_steps_flags_weak_evidence() -> None:
    from video_skill_extractor.postprocess import calibrate_steps

    rows = [
        {
            "step_id": "step_1",
            "enrichment": {
                "vlm_judgement": {
                    "summary": "No evidence detected in the frame",
                    "confidence": 0.95,
                },
                "signal_pass": {"changes_detected": ["no changes"]},
            },
            "transcript_support": {"alignment_confidence": 0.2},
        }
    ]
    out = calibrate_steps(rows, weak_conf_cap=0.25, weak_alignment_threshold=0.4)
    e = out[0]["enrichment"]
    assert e["vlm_judgement"]["confidence"] <= 0.25
    assert e["review_flag"] is True
    assert "weak_visual_evidence" in e["review_reasons"]
    assert e["signal_pass"]["changes_detected"] == []
