import os

from course_step_extractor.ai_adapter import _temporary_env, run_structured
from course_step_extractor.settings import ProviderConfig


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeAgent:
    calls = 0

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

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
    assert len(errors) == 2
    assert errors[0]["stage"] == "unit"
    assert errors[1]["kind"] == "transient_recovered"


def test_run_structured_with_images_backoff(monkeypatch):
    from course_step_extractor import ai_adapter

    class _FlakyAgent:
        calls = 0

        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        def run_sync(self, user_prompt):
            _ = user_prompt
            _FlakyAgent.calls += 1
            if _FlakyAgent.calls == 1:
                raise RuntimeError("Connection error.")
            return _FakeResult({"ok": True})

    sleeps = []

    monkeypatch.setattr(ai_adapter, "Agent", _FlakyAgent)
    monkeypatch.setattr(ai_adapter.time, "sleep", lambda s: sleeps.append(s))

    cfg = ProviderConfig(
        provider="openai-compatible",
        base_url="http://127.0.0.1:8080",
        model="qwen",
    )
    errors = []
    out = ai_adapter.run_structured_with_images(
        cfg,
        "system",
        "user",
        ["data:image/jpeg;base64,ZmFrZQ=="],
        dict,
        max_retries=1,
        error_rows=errors,
        error_context={"stage": "img"},
    )
    assert out == {"ok": True}
    assert len(errors) == 2
    assert errors[0]["stage"] == "img"
    assert errors[1]["kind"] == "transient_recovered"
    assert len(sleeps) == 1
    assert 0.75 <= sleeps[0] <= 0.95


def test_sleep_backoff_zero_is_noop(monkeypatch):
    from course_step_extractor import ai_adapter

    called = []
    monkeypatch.setattr(ai_adapter.time, "sleep", lambda s: called.append(s))
    ai_adapter._sleep_backoff(0)
    assert called == []
