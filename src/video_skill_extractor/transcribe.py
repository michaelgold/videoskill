from __future__ import annotations

import json
from pathlib import Path

import httpx

from video_skill_extractor.settings import ProviderConfig


def transcribe_video_whisper_openai(
    provider: ProviderConfig,
    video_path: Path,
    out_path: Path,
    response_format: str = "verbose_json",
    timestamp_granularities: str = "word,segment",
    language: str = "en",
) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    endpoint = str(provider.base_url).rstrip("/") + "/v1/audio/transcriptions"
    headers: dict[str, str] = {}
    api_key = provider.api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=provider.timeout_s) as client:
        with video_path.open("rb") as f:
            files = {"file": (video_path.name, f, "video/mp4")}
            granularities = [
                g.strip()
                for g in str(timestamp_granularities).split(",")
                if g.strip()
            ]
            data = {
                "model": provider.model,
                "response_format": response_format,
                "timestamp_granularities[]": granularities,
                "without_timestamps": "false",
            }
            if language and language.lower() != "auto":
                data["language"] = language
            res = client.post(endpoint, files=files, data=data, headers=headers)
            res.raise_for_status()
            payload = res.json()

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
