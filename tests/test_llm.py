from types import SimpleNamespace

import pytest

from shared.llm import PRICES, CallRecord, Tracker, cost_usd, extract_xml, llm_call, require_api_key


class FakeClient:
    """Stands in for anthropic.Anthropic: records the request, returns an SDK-shaped response."""

    def __init__(self, text, input_tokens=0, output_tokens=0, cache_read=0, cache_write=0):
        self.last_kwargs = None
        usage = SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        )
        content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
        self._response = SimpleNamespace(content=content, usage=usage)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


def test_extract_xml_returns_inner_text_stripped():
    assert extract_xml("a <x> hi </x> b", "x") == "hi"


def test_extract_xml_missing_tag_returns_empty():
    assert extract_xml("nothing here", "x") == ""


def test_llm_call_records_tokens_and_uses_cache_block():
    fake = FakeClient(text="ok", input_tokens=100, output_tokens=20, cache_read=900, cache_write=0)
    t = Tracker()
    out = llm_call("hello", cached_system="POLICY TEXT", label="route", tracker=t, client=fake, model="claude-haiku-5-5")
    assert out == "ok"
    assert t.calls() == 1 and t.records[0].label == "route" and t.records[0].cache_read_tokens == 900
    system = fake.last_kwargs["system"]
    assert system[0]["text"] == "POLICY TEXT" and system[0]["cache_control"] == {"type": "ephemeral"}


def test_llm_call_without_system_sends_no_system_field():
    fake = FakeClient(text="ok")
    llm_call("hello", client=fake, model="claude-haiku-5-5")
    assert "system" not in fake.last_kwargs


def test_cost_usd_uses_prices_table():
    r = CallRecord("x", "claude-haiku-5-5", 1.0, 1_000_000, 0, 0, 0)
    assert cost_usd(r) == PRICES["claude-haiku-5-5"]["input"]


def test_cost_usd_counts_cache_reads_at_cache_price():
    r = CallRecord("x", "claude-opus-5-5", 1.0, 0, 0, 0, 1_000_000)
    assert cost_usd(r) == PRICES["claude-opus-5-5"]["cache_read"]


def test_require_api_key_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("shared.llm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="Missing ANTHROPIC_API_KEY: add it to .env"):
        require_api_key("claude-haiku-5-5")


# ---------------------------------------------------------------- OpenAI path
class FakeOpenAI:
    """Stands in for openai.OpenAI: records the request, returns a Responses-API-shaped answer."""

    def __init__(self, text, input_tokens=0, output_tokens=0, cached=0):
        self.last_kwargs = None
        usage = SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_tokens_details=SimpleNamespace(cached_tokens=cached),
        )
        self._response = SimpleNamespace(output_text=text, usage=usage)
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


def test_openai_model_uses_responses_api_and_counts_cached_tokens():
    fake = FakeOpenAI(text="ok", input_tokens=1000, output_tokens=50, cached=800)
    t = Tracker()
    out = llm_call("hello", cached_system="POLICY TEXT", system="extra", model="gpt-6-luna", label="route", tracker=t, client=fake)
    assert out == "ok"
    assert fake.last_kwargs["instructions"].startswith("POLICY TEXT") and "extra" in fake.last_kwargs["instructions"]
    assert fake.last_kwargs["input"] == "hello"
    r = t.records[0]
    assert (r.input_tokens, r.cache_read_tokens, r.cache_write_tokens, r.output_tokens) == (200, 800, 0, 50)


def test_openai_prices_present_for_default_models():
    assert {"gpt-6-luna", "gpt-6.1-sol"} <= set(PRICES)


def test_default_model_is_openai():
    from shared.llm import default_model

    assert default_model() == "gpt-6-luna" and default_model("large") == "gpt-6.1-sol"


def test_require_api_key_picks_the_key_for_the_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("shared.llm.load_dotenv", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="Missing OPENAI_API_KEY: add it to .env"):
        require_api_key("gpt-6-luna")
