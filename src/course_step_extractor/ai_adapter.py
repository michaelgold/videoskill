from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, TypeVar

from pydantic_ai import Agent

from course_step_extractor.settings import ProviderConfig

T = TypeVar("T")


@contextmanager
def _temporary_env(vars_map: dict[str, str | None]):
    old = {k: os.environ.get(k) for k in vars_map}
    try:
        for k, v in vars_map.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_structured(
    provider: ProviderConfig,
    system_prompt: str,
    user_prompt: str,
    result_type: type[T],
    *,
    max_retries: int = 2,
    error_rows: list[dict[str, Any]] | None = None,
    error_context: dict[str, Any] | None = None,
) -> T:
    model_name = provider.model
    env = {
        "OPENAI_BASE_URL": str(provider.base_url).rstrip("/"),
        "OPENAI_API_KEY": provider.api_key() or "dummy-local-key",
    }

    last_exc: Exception | None = None
    attempts = max(1, max_retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            with _temporary_env(env):
                agent = Agent(model_name, result_type=result_type, system_prompt=system_prompt)
                result = agent.run_sync(user_prompt)
            return result.data
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if error_rows is not None:
                row = {
                    "kind": "model_parse_or_call_error",
                    "provider": provider.provider,
                    "model": provider.model,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "error": str(exc),
                }
                if error_context:
                    row.update(error_context)
                error_rows.append(row)

    assert last_exc is not None
    raise last_exc
