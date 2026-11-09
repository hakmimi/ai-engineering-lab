"""Build results.md from the run files. Numbers come only from runs/; nothing is estimated.

runs/        main set
runs/test/   held-out test set
runs/smoke/  smoke runs, never read here
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from ndaflow.data import load_answer_key
from ndaflow.run import RUNS_DIR, as_answers
from ndaflow.score import score

RESULTS = Path(__file__).resolve().parent.parent / "results.md"
LEVEL_ORDER = ["0", "1", "2", "3", "0+"]
METRICS = ("label_right", "f1_entailment", "f1_contradiction", "evidence_recall", "evidence_precision", "errors")

HOW_TO_RUN = """\
## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow-contract-nli"
.venv\\Scripts\\python -m ndaflow.run --level 3 --dry-run                # cost estimate only
.venv\\Scripts\\python -m ndaflow.run --level 3 --repeats 3 --yes
.venv\\Scripts\\python -m ndaflow.run --level 3 --repeats 3 --yes --set test
.venv\\Scripts\\python -m ndaflow.report                                  # rewrites this file
```
"""


def _latest_runs(runs_dir: Path) -> dict[str, tuple[Path, dict]]:
    latest = {}
    for path in sorted(runs_dir.glob("level-*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        latest[run["level"]] = (path, run)  # sorted by timestamp in the name, so the last one wins
    return latest


def _row(level: str, run: dict) -> str:
    reps = run["repeats"]
    outs = [o for r in reps for o in r["results"].values()]
    calls = [c for o in outs for c in o["calls"]]
    fresh = sum(c["input_tokens"] + c["cache_write_tokens"] for c in calls)
    cached = sum(c["cache_read_tokens"] for c in calls)
    key = load_answer_key(run.get("set", "main"))  # score against the current key, so a key fix needs no rerun
    rescored = [score(as_answers(r["results"]), key).as_dict() for r in reps]
    s = {k: mean(r[k] for r in rescored) for k in METRICS}
    cells = [
        level,
        run["model"],
        f"{s['label_right']:.0%}",
        f"{s['f1_entailment']:.2f}",
        f"{s['f1_contradiction']:.2f}",
        f"{s['evidence_recall']:.0%}",
        f"{s['evidence_precision']:.0%}",
        f"{mean(o['seconds'] for o in outs):.1f}",
        f"${mean(o['cost_usd'] for o in outs):.4f}",
        f"{len(calls) / len(outs):.1f}",
        f"{cached / (cached + fresh):.0%}" if cached + fresh else "–",
        f"{s['errors']:.1f}",
    ]
    return "| " + " | ".join(cells) + " |"


def _table(runs_dir: Path) -> str:
    runs = _latest_runs(runs_dir) if runs_dir.exists() else {}
    if not runs:
        return "Not run yet.\n"
    lines = [
        "Averages over repeats, from the latest run file of each level. 17 statements per contract. Prompt caching was on at every level.\n",
        "| Level | Model | Label right | F1 entailment | F1 contradiction | Evidence found | Evidence precision | Seconds / contract | $ / contract | Calls / contract | Cached input | Errors / repeat |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(lvl, runs[lvl][1]) for lvl in LEVEL_ORDER if lvl in runs]
    lines.append("\nRun files:\n")
    lines += [f"- `{runs[lvl][0].name}`: {runs[lvl][1]['contracts']} contracts × {len(runs[lvl][1]['repeats'])} repeats" for lvl in LEVEL_ORDER if lvl in runs]
    return "\n".join(lines) + "\n"


def build_results(runs_dir: Path = RUNS_DIR) -> str:
    """results.md: the main set, then the held-out test set (runs_dir/test)."""
    return (
        "# Results\n\n## Main set\n\n30 NDAs from ContractNLI's dev split. Prompts may be tuned on these.\n\n" + _table(runs_dir)
        + "\n## Test set (held out)\n\n30 NDAs from ContractNLI's test split. No prompt was tuned on them.\n\n"
        + _table(runs_dir / "test") + "\n" + HOW_TO_RUN
    )


def main() -> int:
    RESULTS.write_text(build_results(), encoding="utf-8")
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
