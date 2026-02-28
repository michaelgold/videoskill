import os

from course_step_extractor.ai_adapter import _temporary_env, run_structured
from course_step_extractor.settings import ProviderConfig


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeAgent:
    calls = 0

    def __init__(self, model_name, result_type, system_prompt):
        self.model_name = model_name
        self.result_type = result_type
        self.system_prompt = system_prompt

    def run_sync(self, user_prompt):
        _ = user_prompt
        _FakeAgent.calls += 1
        if _FakeAgent.calls == 1:
            raise RuntimeError("first failure")
        return _FakeResult({"ok": True})


def test_temporary_env_restores(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "old")
    with _temporary_env({"OPENAI_BASE_URL": "new", "OPENAI_API_KEY": "x"}):
        assert os.environ["OPENAI_BASE_URL"] == "new"
        assert os.environ["OPENAI_API_KEY"] == "x"
    assert os.environ["OPENAI_BASE_URL"] == "old"


def test_run_structured_retries_and_logs(monkeypatch):
    from course_step_extractor import ai_adapter

    _FakeAgent.calls = 0
    monkeypatch.setattr(ai_adapter, "Agent", _FakeAgent)

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="qwen",
    )
    errors = []
    out = run_structured(
        cfg,
        "system",
        "user",
        dict,
        max_retries=1,
        error_rows=errors,
        error_context={"stage": "unit"},
    )
    assert out == {"ok": True}
    assert len(errors) == 1
    assert errors[0]["stage"] == "unit"
