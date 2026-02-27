from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TypeVar

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
) -> T:
    model_name = provider.model
    # For OpenAI-compatible servers, pydantic-ai reads OpenAI env vars.
    env = {
        "OPENAI_BASE_URL": str(provider.base_url).rstrip("/"),
        "OPENAI_API_KEY": provider.api_key() or "dummy-local-key",
    }
    with _temporary_env(env):
        agent = Agent(model_name, result_type=result_type, system_prompt=system_prompt)
        result = agent.run_sync(user_prompt)
    return result.data
