from course_step_extractor.chunking import TranscriptChunk
from course_step_extractor.extractor_ai import extract_steps_from_chunks_ai
from course_step_extractor.settings import ProviderConfig


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):
        _ = args, kwargs
        content = {
            "steps": [
                {
                    "instruction_text": "Add a cube",
                    "intent": "Create base mesh",
                    "expected_outcome": "Cube appears",
                    "start_s": 1.0,
                    "end_s": 4.0,
                    "confidence": 0.9,
                }
            ]
        }
        return _Resp({"choices": [{"message": {"content": __import__("json").dumps(content)}}]})


def test_extract_steps_from_chunks_ai(monkeypatch) -> None:
    monkeypatch.setattr(
        "course_step_extractor.extractor_ai.httpx.Client",
        lambda *a, **k: _Client(),
    )

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
