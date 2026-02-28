from course_step_extractor.chunking import TranscriptChunk
from course_step_extractor.extractor_ai import (
    ChunkStep,
    ChunkStepResponse,
    extract_steps_from_chunks_ai,
)
from course_step_extractor.settings import ProviderConfig


def test_extract_steps_from_chunks_ai(monkeypatch) -> None:
    def _fake_run_structured(_provider, _system, _user, _result_type, **kwargs):
        return ChunkStepResponse(
            steps=[
                ChunkStep(
                    instruction_text="Add a cube",
                    intent="Create base mesh",
                    expected_outcome="Cube appears",
                    start_s=1.0,
                    end_s=4.0,
                    confidence=0.9,
                )
            ]
        )

    monkeypatch.setattr("course_step_extractor.extractor_ai.run_structured", _fake_run_structured)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="qwen",
    )
    chunks = [
        TranscriptChunk(
            chunk_id="chunk_1",
            start_s=0.0,
            end_s=10.0,
            segment_ids=["1"],
            text="Now add a cube",
        ),
    ]

    steps = extract_steps_from_chunks_ai(cfg, chunks)
    assert len(steps) == 1
    assert steps[0].instruction_text == "Add a cube"
    assert steps[0].start_s == 1.0



def test_extract_steps_from_chunks_ai_dedupes(monkeypatch) -> None:
    def _fake_run_structured(_provider, _system, _user, _result_type, **kwargs):
        _ = kwargs
        return ChunkStepResponse(
            steps=[
                ChunkStep(
                    instruction_text="Add a cube",
                    intent="Create base mesh",
                    expected_outcome="Cube appears",
                    start_s=1.0,
                    end_s=4.0,
                    confidence=0.9,
                ),
                ChunkStep(
                    instruction_text="  add   a   CUBE  ",
                    intent="Create base mesh",
                    expected_outcome="Cube appears",
                    start_s=2.0,
                    end_s=5.0,
                    confidence=0.8,
                ),
            ]
        )

    monkeypatch.setattr("course_step_extractor.extractor_ai.run_structured", _fake_run_structured)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="qwen",
    )
    chunks = [
        TranscriptChunk(
            chunk_id="chunk_1",
            start_s=0.0,
            end_s=10.0,
            segment_ids=["1"],
            text="Now add a cube",
        )
    ]

    steps = extract_steps_from_chunks_ai(cfg, chunks)
    assert len(steps) == 1
    assert steps[0].step_id == "step_1"
