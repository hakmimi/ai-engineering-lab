from types import SimpleNamespace

import pytest

from tablefind.embed import EMBED_USD_PER_M, MAX_CHARS, Embedder, cosine_top_k


class FakeEmbeddings:
    """Stands in for openai.OpenAI().embeddings: vector = [len(text), 1.0]; 10 tokens per text."""

    def __init__(self):
        self.calls = []

    def create(self, model, input):
        self.calls.append((model, list(input)))
        data = [SimpleNamespace(embedding=[float(len(t)), 1.0]) for t in input]
        return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=10 * len(input)))


def _fake():
    f = FakeEmbeddings()
    return SimpleNamespace(embeddings=f), f


def test_cache_hit_makes_no_call(tmp_path):
    client, fake = _fake()
    Embedder(tmp_path, client=client).embed(["a", "bb"])
    again = Embedder(tmp_path, client=client)  # a new object reads the cache from disk
    assert again.embed(["bb", "a"]) == [[2.0, 1.0], [1.0, 1.0]]
    assert len(fake.calls) == 1


def test_cache_key_changes_with_text_and_model(tmp_path):
    client, fake = _fake()
    Embedder(tmp_path, client=client).embed(["a"])
    Embedder(tmp_path, client=client).embed(["a "])
    Embedder(tmp_path, client=client, model="other-model").embed(["a"])
    assert len(fake.calls) == 3


def test_long_text_is_truncated_before_call(tmp_path):
    client, fake = _fake()
    Embedder(tmp_path, client=client).embed(["x" * (MAX_CHARS + 500)])
    assert len(fake.calls[0][1][0]) == MAX_CHARS


def test_cost_counts_only_misses(tmp_path):
    client, _ = _fake()
    e = Embedder(tmp_path, client=client)
    e.embed(["a", "b"])
    e.embed(["a", "b", "c"])
    assert e.cost_usd == pytest.approx(30 * EMBED_USD_PER_M / 1_000_000)


def test_batches_of_100(tmp_path):
    client, fake = _fake()
    Embedder(tmp_path, client=client).embed([str(i) for i in range(250)])
    assert [len(c[1]) for c in fake.calls] == [100, 100, 50]


def test_cosine_top_k():
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]
    assert cosine_top_k([1.0, 0.1], vecs, ["x", "y", "z"], 2) == ["x", "z"]


def test_cosine_top_k_accepts_prenormalized_vectors():
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]]
    assert cosine_top_k([1.0, 0.1], vecs, ["x", "y", "z"], 2, normalized=True) == ["x", "z"]
