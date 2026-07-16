from dataclasses import replace

from pokedb.api_client import ApiClient
from pokedb.config import load_config
from pokedb.utils.file_ops import get_cache_path


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"result": "fresh"}


class FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return FakeResponse()


def test_api_client_refetches_an_unreadable_cache_entry(tmp_path, monkeypatch):
    url = "https://example.test/resource"
    client = ApiClient(
        replace(
            load_config(),
            timeout=5,
            max_retries=0,
            parser_cache_dir=tmp_path,
            cache_expires=60,
        )
    )
    cache_path = get_cache_path(url, str(tmp_path))
    cache_path.write_text("not json", encoding="utf-8")
    session = FakeSession()
    monkeypatch.setattr(client, "_get_session", lambda: session)

    assert client.get(url) == {"result": "fresh"}
    assert session.calls == 1
    assert "fresh" in cache_path.read_text(encoding="utf-8")


def test_api_client_uses_cache_without_expiration(tmp_path, monkeypatch):
    url = "https://example.test/resource"
    client = ApiClient(
        replace(
            load_config(),
            parser_cache_dir=tmp_path,
            cache_expires=None,
        )
    )
    cache_path = get_cache_path(url, tmp_path)
    cache_path.write_text('{"result": "cached"}', encoding="utf-8")
    session = FakeSession()
    monkeypatch.setattr(client, "_get_session", lambda: session)

    assert client.get(url) == {"result": "cached"}
    assert session.calls == 0
