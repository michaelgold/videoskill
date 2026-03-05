import json
from pathlib import Path

from video_skill_extractor.settings import TranscriptionConfig
from video_skill_extractor.transcribe import transcribe_video_whisper_openai


class _Resp:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_url = None
        self.last_data = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, files=None, data=None, headers=None):
        _ = files, headers
        self.last_url = url
        self.last_data = data
        return _Resp(self.payload)


def test_transcribe_video_whisper_openai(monkeypatch, tmp_path: Path) -> None:
    payload = {"segments": [{"id": 0, "start": 0.0, "end": 1.0, "text": "hi"}]}
    fake = _Client(payload)

    class _Factory:
        def __call__(self, *args, **kwargs):
            return fake

    monkeypatch.setattr("video_skill_extractor.transcribe.httpx.Client", _Factory())

    cfg = TranscriptionConfig(
        provider="speaches",
        base_url="http://localhost:8000",
        model="Systran/faster-whisper-medium",
        timeout_s=30,
    )
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    out = tmp_path / "whisper.json"

    result = transcribe_video_whisper_openai(cfg, video, out)
    assert result["segments"][0]["text"] == "hi"
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["segments"][0]["id"] == 0
    assert fake.last_url.endswith("/v1/audio/transcriptions")
    assert fake.last_data["model"] == "Systran/faster-whisper-medium"
    assert "word" in fake.last_data["timestamp_granularities[]"]
    assert fake.last_data["language"] == "en"


def test_transcribe_video_whisper_openai_auto_language_omits_field(
    monkeypatch, tmp_path: Path
) -> None:
    payload = {"segments": []}
    fake = _Client(payload)

    class _Factory:
        def __call__(self, *args, **kwargs):
            return fake

    monkeypatch.setattr("video_skill_extractor.transcribe.httpx.Client", _Factory())

    cfg = TranscriptionConfig(
        provider="speaches",
        base_url="http://localhost:8000",
        model="Systran/faster-whisper-medium",
        timeout_s=30,
    )
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"video")
    out = tmp_path / "whisper.json"

    transcribe_video_whisper_openai(cfg, video, out, language="auto")
    assert "language" not in fake.last_data
