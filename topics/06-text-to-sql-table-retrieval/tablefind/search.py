"""Keyword search (BM25) and ranking helpers. No dependencies."""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def tokens(text: str) -> list[str]:
    """Lowercase words; splits snake_case, CamelCase and digits ("ArtifactTag" -> artifact, tag)."""
    return [w.lower() for w in _WORD.findall(text)]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / len(docs) if docs else 0.0
        df = Counter(w for d in docs for w in set(d))
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, n in zip(self.tf, self.len):
            s = 0.0
            for w in query:
                f = tf.get(w, 0)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * n / self.avg))
            out.append(s)
        return out


def top_k(scores: list[float], ids: list[str], k: int) -> list[str]:
    """Highest score first; ties broken by id so runs are repeatable."""
    return [i for _, i in sorted(zip(scores, ids), key=lambda p: (-p[0], p[1]))[:k]]
