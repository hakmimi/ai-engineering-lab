"""Build results.md from the run files. Numbers come only from runs/; nothing is estimated."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from claimsflow.run import RUNS_DIR

RESULTS = Path(__file__).resolve().parent.parent / "results.md"
LEVEL_ORDER = ["0", "1", "2", "3", "0+"]

HOW_TO_RUN = """\
## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow"
.venv\\Scripts\\python -m claimsflow.run --level 3 --dry-run     # cost estimate only
.venv\\Scripts\\python -m claimsflow.run --level 3 --repeats 3 --yes
.venv\\Scripts\\python -m claimsflow.run --level 3 --repeats 3 --yes --set hard
.venv\\Scripts\\python -m claimsflow.report                       # rewrites this file
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
    s = {k: mean(r["scores"][k] for r in reps) for k in ("decision_right", "amount_right", "doc_caught", "doc_false_alarms", "errors")}
    cells = [
        level,
        run["model"],
        f"{s['decision_right']:.0%}",
        f"{s['amount_right']:.0%}",
        f"{s['doc_caught']:.0%}",
        f"{s['doc_false_alarms']:.0%}",
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
        "Averages over repeats, from the latest run file of each level. Prompt caching was on at every level.\n",
        "| Level | Model | Decision right | Amount right | Doc problems caught | False doc alarms | Seconds / claim | $ / claim | Calls / claim | Cached input | Errors / repeat |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines += [_row(lvl, runs[lvl][1]) for lvl in LEVEL_ORDER if lvl in runs]
    lines.append("\nRun files:\n")
    lines += [f"- `{runs[lvl][0].name}`: {runs[lvl][1]['claims']} claims × {len(runs[lvl][1]['repeats'])} repeats" for lvl in LEVEL_ORDER if lvl in runs]
    return "\n".join(lines) + "\n"


def build_report(runs_dir: Path = RUNS_DIR) -> str:
    """One set's results as a page."""
    return "# Results\n\n" + _table(runs_dir) + "\n" + HOW_TO_RUN


def build_results(runs_dir: Path = RUNS_DIR) -> str:
    """results.md: the main set, then the hard held-out set (runs_dir/hard)."""
    return (
        "# Results\n\n## Main set\n\n" + _table(runs_dir)
        + "\n## Hard set\n\nHeld-out claims (`data/hard/`): longer documents, extra attachments, sums and conflicting numbers. "
        "No prompt was tuned on them.\n\n" + _table(runs_dir / "hard") + "\n" + HOW_TO_RUN
    )


def main() -> int:
    RESULTS.write_text(build_results(), encoding="utf-8")
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
