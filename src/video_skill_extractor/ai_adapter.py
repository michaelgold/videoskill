from __future__ import annotations

import os
import random
import time
from contextlib import contextmanager
from typing import Any, TypeVar

from pydantic_ai import Agent
from pydantic_ai.messages import ImageUrl
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from video_skill_extractor.settings import ProviderConfig

T = TypeVar("T")


def _sleep_backoff(attempt: int) -> None:
    if attempt <= 0:
        return
    base = 0.75 * (2 ** (attempt - 1))
    jitter = random.uniform(0.0, base * 0.25)
    time.sleep(base + jitter)


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


def _build_openai_agent(
    provider: ProviderConfig,
    result_type: type[T],
    system_prompt: str,
) -> Agent[T]:
    model = OpenAIChatModel(
        provider.model,
        provider=OpenAIProvider(
            base_url=str(provider.base_url).rstrip("/"),
            api_key=provider.api_key() or "dummy-local-key",
        ),
    )
    return Agent(model, output_type=result_type, system_prompt=system_prompt)


def run_structured(
    provider: ProviderConfig,
    system_prompt: str,
    user_prompt: str,
    result_type: type[T],
    *,
    max_retries: int = 5,
    error_rows: list[dict[str, Any]] | None = None,
    error_context: dict[str, Any] | None = None,
) -> T:
    last_exc: Exception | None = None
    attempts = max(1, max_retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            agent = _build_openai_agent(provider, result_type, system_prompt)
            result = agent.run_sync(user_prompt)
            if attempt > 1 and error_rows is not None:
                row = {
                    "kind": "transient_recovered",
                    "provider": provider.provider,
                    "model": provider.model,
                    "resolved_on_attempt": attempt,
                }
                if error_context:
                    row.update(error_context)
                error_rows.append(row)
            if hasattr(result, "output"):
                return result.output
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
            if attempt < attempts:
                _sleep_backoff(attempt)

    assert last_exc is not None
    if error_rows is not None:
        row = {
            "kind": "unresolved_final",
            "provider": provider.provider,
            "model": provider.model,
            "error": str(last_exc),
        }
        if error_context:
            row.update(error_context)
        error_rows.append(row)
    raise last_exc


def run_structured_with_images(
    provider: ProviderConfig,
    system_prompt: str,
    user_prompt: str,
    image_urls: list[str],
    result_type: type[T],
    *,
    max_retries: int = 5,
    error_rows: list[dict[str, Any]] | None = None,
    error_context: dict[str, Any] | None = None,
) -> T:
    last_exc: Exception | None = None
    attempts = max(1, max_retries + 1)
    user_parts: list[Any] = [user_prompt] + [ImageUrl(url) for url in image_urls]
    for attempt in range(1, attempts + 1):
        try:
            agent = _build_openai_agent(provider, result_type, system_prompt)
            result = agent.run_sync(user_parts)
            if attempt > 1 and error_rows is not None:
                row = {
                    "kind": "transient_recovered",
                    "provider": provider.provider,
                    "model": provider.model,
                    "resolved_on_attempt": attempt,
                }
                if error_context:
                    row.update(error_context)
                error_rows.append(row)
            if hasattr(result, "output"):
                return result.output
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
            msg = str(exc).lower()
            transient = (
                "connection error" in msg
                or "connection reset" in msg
                or "503" in msg
                or "service unavailable" in msg
                or "server disconnected" in msg
                or "timed out" in msg
            )
            if transient and attempt < attempts:
                _sleep_backoff(attempt)

    assert last_exc is not None
    if error_rows is not None:
        row = {
            "kind": "unresolved_final",
            "provider": provider.provider,
            "model": provider.model,
            "error": str(last_exc),
        }
        if error_context:
            row.update(error_context)
        error_rows.append(row)
    raise last_exc
