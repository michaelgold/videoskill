from course_step_extractor.enrich import (
    enrich_steps,
    plan_sampling_for_step,
    sample_timestamps,
)
from course_step_extractor.models import TutorialStep


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
