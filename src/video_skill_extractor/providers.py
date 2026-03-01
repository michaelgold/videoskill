from __future__ import annotations

import httpx

from video_skill_extractor.settings import ProviderConfig


def ping_provider(config: ProviderConfig, path: str = "/") -> dict[str, object]:
    headers: dict[str, str] = {}
    key = config.api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    url = str(config.base_url).rstrip("/") + path
    with httpx.Client(timeout=config.timeout_s, follow_redirects=True) as client:
        response = client.get(url, headers=headers)

    return {
        "ok": response.status_code < 500,
        "status_code": response.status_code,
        "url": url,
    }
