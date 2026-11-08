"""Tests never reach a real API: any attempt to build a real client fails the test."""

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _blocked(model):
        raise AssertionError(f"a test tried to call the real API ({model})")

    monkeypatch.setattr("shared.llm._default_client", _blocked)
