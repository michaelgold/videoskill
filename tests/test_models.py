import pytest

from video_skill_extractor.models import Step, TranscriptSegment, TutorialStep


def test_step_model_validates_required_fields() -> None:
    step = Step(title="A", description="B")
    assert step.title == "A"
    assert step.description == "B"


@pytest.mark.parametrize(
    "payload",
    [{"title": "", "description": "x"}, {"title": "x", "description": ""}],
)
def test_step_model_rejects_empty_fields(payload: dict[str, str]) -> None:
    with pytest.raises(Exception):
        Step(**payload)


def test_transcript_segment_time_validation() -> None:
    seg = TranscriptSegment(segment_id="1", start_s=0.0, end_s=1.2, text="hello")
    assert seg.end_s == 1.2

    with pytest.raises(Exception):
        TranscriptSegment(segment_id="2", start_s=2.0, end_s=1.0, text="bad")


def test_tutorial_step_bounds() -> None:
    step = TutorialStep(
        step_id="s1",
        source_segment_id="1",
        start_s=0.0,
        end_s=1.0,
        clip_start_s=0.0,
        clip_end_s=1.2,
        instruction_text="Do thing",
        intent="Create geometry",
        expected_outcome="Mesh appears",
        confidence=0.8,
    )
    assert step.confidence == 0.8

    with pytest.raises(Exception):
        TutorialStep(
            step_id="s2",
            source_segment_id="2",
            start_s=0.0,
            end_s=1.0,
            clip_start_s=0.0,
            clip_end_s=1.0,
            instruction_text="x",
            intent="y",
            expected_outcome="z",
            confidence=1.2,
        )
