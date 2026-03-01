from video_skill_extractor.providers import ping_provider
from video_skill_extractor.settings import ProviderConfig


class _Resp:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _Client:
    def __init__(self, status_code: int):
        self._status = status_code
        self.last_headers = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _url, headers=None):
        self.last_headers = headers
        return _Resp(self._status)


def test_ping_provider_ok(monkeypatch) -> None:
    fake = _Client(200)

    class _Factory:
        def __call__(self, *args, **kwargs):
            return fake

    monkeypatch.setattr("video_skill_extractor.providers.httpx.Client", _Factory())
    cfg = ProviderConfig(provider="x", base_url="http://127.0.0.1:8000", model="m")
    result = ping_provider(cfg, path="/v1/models")
    assert result["ok"] is True
    assert result["status_code"] == 200


def test_ping_provider_includes_auth_header(monkeypatch) -> None:
    fake = _Client(404)

    class _Factory:
        def __call__(self, *args, **kwargs):
            return fake

    monkeypatch.setattr("video_skill_extractor.providers.httpx.Client", _Factory())
    monkeypatch.setenv("TEST_API_KEY", "secret")
    cfg = ProviderConfig(
        provider="x",
        base_url="http://127.0.0.1:8000",
        model="m",
        api_key_env="TEST_API_KEY",
    )
    result = ping_provider(cfg)
    assert result["ok"] is True  # 404 is still non-5xx
    assert fake.last_headers == {"Authorization": "Bearer secret"}

    monkeypatch.delenv("TEST_API_KEY", raising=False)
