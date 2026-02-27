from pathlib import Path

from course_step_extractor.render import render_markdown, write_markdown


def test_render_markdown_basic(tmp_path: Path) -> None:
    steps = [
        {
            "step_id": "step_1",
            "instruction_text": "Add a cube",
            "intent": "Create base",
            "expected_outcome": "Cube appears",
            "start_s": 1.0,
            "end_s": 3.0,
            "clip_start_s": 0.5,
            "clip_end_s": 3.5,
            "enrichment": {
                "sampling": {"count": 3, "rationale": "duration", "timestamps": [0.5, 2.0, 3.5]},
                "vlm_judgement": {"summary": "visible", "confidence": 0.8},
            },
        }
    ]
    md = render_markdown(steps, title="Demo")
    assert "# Demo" in md
    assert "## Step 1: Add a cube" in md
    assert "Timecode" in md

    out = tmp_path / "lesson.md"
    write_markdown(md, out)
    assert out.exists()
