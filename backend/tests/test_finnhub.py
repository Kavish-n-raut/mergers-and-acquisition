import types

import pytest

import app.services.finnhub_client as fc


class _FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = str(data)

    def json(self):
        return self._data


def _configure(monkeypatch, key="testkey"):
    monkeypatch.setattr(fc, "get_settings", lambda: types.SimpleNamespace(finnhub_api_key=key))


def test_quote_parsing(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        fc.requests, "get",
        lambda url, params=None, timeout=None: _FakeResp({"c": 150.0, "d": 2.0, "dp": 1.35, "h": 151, "l": 148, "o": 149, "pc": 148, "t": 123}),
    )
    q = fc.get_quote("aapl")
    assert q["symbol"] == "AAPL"
    assert q["current_price"] == 150.0
    assert q["percent_change"] == 1.35
    assert q["previous_close"] == 148


def test_news_parsing(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        fc.requests, "get",
        lambda url, params=None, timeout=None: _FakeResp([
            {"headline": "Company beats earnings", "summary": "Strong quarter", "source": "Reuters", "url": "http://x", "datetime": 1},
            {"headline": "Guidance raised", "summary": "", "source": "AP", "url": "http://y", "datetime": 2},
        ]),
    )
    news = fc.get_company_news("MSFT", days=30, limit=10)
    assert news["count"] == 2
    assert news["articles"][0]["headline"] == "Company beats earnings"


def test_not_configured_raises(monkeypatch):
    _configure(monkeypatch, key=None)
    assert fc.is_configured() is False
    with pytest.raises(fc.FinnhubConfigurationError):
        fc.get_quote("AAPL")


def test_rate_limit_raises(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(fc.requests, "get", lambda url, params=None, timeout=None: _FakeResp({}, status=429))
    with pytest.raises(fc.FinnhubError):
        fc.get_quote("AAPL")
