"""Turn the downloaded ContractNLI files into the two small sets this topic uses.

    python -m ndaflow.build_data <path to the unzipped contract-nli folder>

Main set: 30 NDAs from dev.json (prompts may be tuned on it).
Test set: 30 NDAs from test.json (held out, never tuned on).
train.json is never read.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from ndaflow.data import DATA, SETS
from ndaflow.models import STATEMENT_IDS

SEED = 2026
N = 30
SOURCE = "ContractNLI (Koreeda & Manning, 2021), https://stanfordnlp.github.io/contract-nli/"
LABEL_MAP = {"Entailment": "entailment", "Contradiction": "contradiction", "NotMentioned": "not_mentioned"}
SPLIT_FOR_SET = {"main": "dev", "test": "test"}

NOTICE = f"""\
# Data notice

The contracts and labels in `main.json` and `test.json` come from **ContractNLI**:

> Yuta Koreeda and Christopher D. Manning. 2021. ContractNLI: A Dataset for Document-level Natural Language
> Inference for Contracts. Findings of the Association for Computational Linguistics: EMNLP 2021.
> https://stanfordnlp.github.io/contract-nli/

ContractNLI is released by Hitachi America, Ltd. under the Creative Commons Attribution 4.0 International
licence (CC BY 4.0, https://creativecommons.org/licenses/by/4.0/).

What was changed: 60 of the 607 NDAs were drawn at random (seed {SEED}): {N} from the dev split (`main.json`)
and {N} from the test split (`test.json`). Each NDA is stored as its list of spans (the dataset's own
sentence/list-item split, whitespace trimmed); the contract text itself is unchanged. Labels were renamed
(Entailment → entailment, Contradiction → contradiction, NotMentioned → not_mentioned). The 17 statements in
`statements.json` are the dataset's hypotheses, unchanged.
"""


def _contract(doc: dict) -> dict:
    text = doc["text"]
    annotations = doc["annotation_sets"][0]["annotations"]
    return {
        "doc_id": str(doc["id"]),
        "file_name": doc["file_name"],
        "url": doc.get("url", ""),
        "spans": [text[s:e].strip() for s, e in doc["spans"]],
        "key": {
            sid: {"label": LABEL_MAP[annotations[sid]["choice"]], "evidence": sorted(annotations[sid]["spans"])}
            for sid in STATEMENT_IDS
            if sid in annotations
        },
    }


def build_set(raw: dict, n: int, seed: int) -> list[dict]:
    """Draw n documents at random (fixed seed) and return them sorted by dataset id."""
    docs = sorted(raw["documents"], key=lambda d: d["id"])
    chosen = random.Random(seed).sample(docs, n)
    return [_contract(d) for d in sorted(chosen, key=lambda d: d["id"])]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m ndaflow.build_data <path to the unzipped contract-nli folder>")
        return 2
    folder = Path(argv[0])
    DATA.mkdir(parents=True, exist_ok=True)
    labels = None
    for set_name, split in SPLIT_FOR_SET.items():
        raw = json.loads((folder / f"{split}.json").read_text(encoding="utf-8"))
        labels = raw["labels"]
        contracts = build_set(raw, N, SEED)
        out = {"source": SOURCE, "licence": "CC BY 4.0", "split": split, "seed": SEED, "contracts": contracts}
        SETS[set_name].write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{set_name}: {len(contracts)} contracts ({split})")
    statements = [{"sid": sid, "short": labels[sid]["short_description"], "text": labels[sid]["hypothesis"]} for sid in STATEMENT_IDS]
    (DATA / "statements.json").write_text(json.dumps(statements, indent=1, ensure_ascii=False), encoding="utf-8")
    (DATA / "NOTICE.md").write_text(NOTICE, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
