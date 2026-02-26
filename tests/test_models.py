import pytest

from course_step_extractor.models import Step


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
