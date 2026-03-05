from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError


class ProviderConfig(BaseModel):
    provider: str = Field(min_length=1)
    base_url: AnyHttpUrl
    model: str = Field(min_length=1)
    api_key_env: str | None = None
    timeout_s: float = Field(default=30.0, gt=0)

    def api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        return os.getenv(self.api_key_env)


class TranscriptionConfig(ProviderConfig):
    language: str = "en"


class AppConfig(BaseModel):
    transcription: TranscriptionConfig
    reasoning: ProviderConfig
    vlm: ProviderConfig

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(payload)


def validate_config(path: Path) -> tuple[bool, str]:
    try:
        AppConfig.load(path)
    except FileNotFoundError:
        return False, f"Config file not found: {path}"
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON: {exc}"
    except ValidationError as exc:
        return False, f"Validation error: {exc}"
    return True, "OK"
