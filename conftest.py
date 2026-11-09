"""Tests never reach a real API: any attempt to build a real client fails the test."""

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(model):
        raise AssertionError(f"a test tried to call the real API ({model})")

    monkeypatch.setattr("shared.llm._default_client", _blocked)
    monkeypatch.setattr("ndaspeed.config.make_client", lambda *a, **k: _blocked("ndaspeed client"))  # topic 3
    # and never read the real .env: its settings (CLAIMS_MODEL, keys) must not leak into tests
    monkeypatch.setattr("shared.llm.load_dotenv", lambda *a, **k: None)
