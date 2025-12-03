import types

import tools.sampler as sampler


class DummyResponse:
    def __init__(self, ok=True, results=None):
        self.ok = ok
        self._results = results or []

    def json(self):
        return {"results": self._results}


def test_get_urls_lorem(monkeypatch):
    monkeypatch.setattr(sampler, "SOURCE", "lorem")
    urls = sampler.get_urls("test-term", 3)
    assert len(urls) == 3
    assert all(u.startswith("lorem://test-term#") for u in urls)


def test_get_urls_openverse(monkeypatch):
    monkeypatch.setattr(sampler, "SOURCE", "openverse")

    def fake_get(url, params=None, timeout=None, headers=None):
        return DummyResponse(ok=True, results=[{"url": "http://img/1"}, {"url": None}])

    monkeypatch.setattr(sampler.requests, "get", fake_get)
    urls = sampler.get_urls("hat", 2)
    assert urls == ["http://img/1"]


def test_get_urls_vinted_dispatch(monkeypatch):
    calls = []

    def fake_vinted(q, limit):
        calls.append((q, limit))
        return ["http://vinted/1"]

    monkeypatch.setattr(sampler, "SOURCE", "vinted")
    monkeypatch.setattr(sampler, "get_vinted_urls", fake_vinted)
    urls = sampler.get_urls("boots", 1)
    assert urls == ["http://vinted/1"]
    assert calls == [("boots", 1)]
