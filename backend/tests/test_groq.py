import types

import pytest

import app.services.groq_client as gc


class _FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = str(data)

    def json(self):
        return self._data


def _configure(monkeypatch, key="gsk_test"):
    monkeypatch.setattr(gc, "get_settings", lambda: types.SimpleNamespace(groq_api_key=key, groq_model="llama-3.3-70b-versatile"))


def test_generate_text_parses_choice(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        gc.requests, "post",
        lambda url, json=None, headers=None, timeout=None: _FakeResp({"choices": [{"message": {"content": "Hello world"}}]}),
    )
    assert gc.generate_text("hi") == "Hello world"


def test_generate_json_parses_object(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        gc.requests, "post",
        lambda url, json=None, headers=None, timeout=None: _FakeResp({"choices": [{"message": {"content": '{"risks": [{"risk_category": "X"}]}'}}]}),
    )
    out = gc.generate_json("extract")
    assert out["risks"][0]["risk_category"] == "X"


def test_not_configured_raises(monkeypatch):
    _configure(monkeypatch, key=None)
    assert gc.is_configured() is False
    with pytest.raises(gc.GroqConfigurationError):
        gc.generate_text("hi")


def test_bad_key_raises_config_error(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(gc.requests, "post", lambda url, json=None, headers=None, timeout=None: _FakeResp({}, status=401))
    with pytest.raises(gc.GroqConfigurationError):
        gc.generate_text("hi")
