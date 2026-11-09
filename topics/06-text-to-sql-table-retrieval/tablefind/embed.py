"""Embeddings with a disk cache, and cosine ranking in plain Python (no numpy in the venv).

The cache file is one JSON line per text: {"k": sha256(model + text), "v": [...]}. A changed card or model
gives a new key, so stale vectors are never reused. Only cache misses cost money.
"""

from __future__ import annotations

import hashlib
import json
import math
from operator import mul
from pathlib import Path

EMBED_MODEL = "text-embedding-3-small"
EMBED_USD_PER_M = 0.02
MAX_CHARS = 24000  # about 6k tokens: under the model's 8,191-token limit even for dense text
BATCH = 100


def _key(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


class Embedder:
    def __init__(self, cache_dir: Path, client=None, model: str = EMBED_MODEL):
        self.model, self.client, self.cost_usd = model, client, 0.0
        self.path = cache_dir / f"{model}.jsonl"
        self.cache: dict[str, list[float]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self.cache[row["k"]] = row["v"]

    def _client(self):
        if self.client is None:
            import openai
            self.client = openai.OpenAI(max_retries=4)
        return self.client

    def embed(self, texts: list[str]) -> list[list[float]]:
        keys = [_key(self.model, t) for t in texts]
        todo = list(dict.fromkeys((k, t) for k, t in zip(keys, texts) if k not in self.cache))
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            resp = self._client().embeddings.create(model=self.model, input=[t[:MAX_CHARS] for _, t in chunk])
            self.cost_usd += resp.usage.total_tokens * EMBED_USD_PER_M / 1_000_000
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                for (k, _), d in zip(chunk, resp.data):
                    self.cache[k] = list(d.embedding)
                    f.write(json.dumps({"k": k, "v": self.cache[k]}) + "\n")
        return [self.cache[k] for k in keys]


def normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine_top_k(q: list[float], vecs: list[list[float]], ids: list[str], k: int) -> list[str]:
    """vecs may be pre-normalized; q is normalized here. Ties broken by id."""
    qn = normalize(q)
    scores = [sum(map(mul, qn, normalize(v))) for v in vecs]
    return [i for _, i in sorted(zip(scores, ids), key=lambda p: (-p[0], p[1]))[:k]]
