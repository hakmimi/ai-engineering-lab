"""Build results.md from the run files. Numbers come only from runs/.

runs/        main set
runs/test/   held-out set
runs/smoke/  smoke runs, never read here
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from sqlloop.data import TOPIC_DIR, load_set
from sqlloop.models import DIFFICULTIES
from sqlloop.run import RUNS_DIR, spent_in_runs
from sqlloop.score import score

RESULTS = TOPIC_DIR / "results.md"
LEVEL_ORDER = ["0", "1", "2", "3", "0+", "4", "5"]
NAMES = {"0": "0 · one prompt", "1": "1 · AI grader reads", "2": "2 · run it", "3": "3 · AI grader sees rows", "0+": "0+ · bigger model",
         "4": "4 · bigger model grades, reads", "5": "5 · bigger model grades, sees rows"}


def _latest(runs_dir: Path) -> dict[str, dict]:
    latest = {}
    for path in sorted(runs_dir.glob("level-*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        latest[run["level"]] = run
    return latest


def _pct(v):
    return "–" if v is None else f"{v:.0%}"


def _avg(scores, k):
    vals = [s[k] for s in scores if s[k] is not None]
    return mean(vals) if vals else None


def _lenient(runs_dir: Path) -> dict:
    path = RUNS_DIR / "lenient.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build(runs_dir: Path, difficulty: dict, set_name: str = "main") -> str:
    latest = _latest(runs_dir)
    lenient = _lenient(runs_dir)
    if not latest:
        return "_Not run yet._\n"
    head = ("| Level | Model | Right | Right, extra columns forgiven | First try right | Fixed | Broken | PASS on wrong | False alarm | PASS is right | "
            "Rounds | Cap hit | API errors | s / question | $ / question |\n|" + "---|" * 15)
    rows, diff_rows = [head], ["| Level | " + " | ".join(DIFFICULTIES) + " |\n|---|" + "---|" * len(DIFFICULTIES)]
    for lvl in [l for l in LEVEL_ORDER if l in latest]:
        run = latest[lvl]
        scores = [score(r["results"], difficulty) for r in run["repeats"]]
        outs = [o for r in run["repeats"] for o in r["results"].values()]
        rows.append("| " + " | ".join([
            lvl, run["model"] + (f" + {run['grader_model']} grades" if run.get("grader_model") and run["grader_model"] != run["model"] else ""), _pct(_avg(scores, "right")),
            _pct(mean(lenient[f"{set_name}/{lvl}/{run['created']}"])) if f"{set_name}/{lvl}/{run['created']}" in lenient else "–",
            _pct(_avg(scores, "first_right")),
            f"{mean(s['fixed'] for s in scores):.1f}", f"{mean(s['broken'] for s in scores):.1f}",
            _pct(_avg(scores, "pass_on_wrong")), _pct(_avg(scores, "false_alarm")), _pct(_avg(scores, "pass_right")),
            f"{_avg(scores, 'rounds'):.2f}", _pct(_avg(scores, "cap_hit")), str(sum(s["api_errors"] for s in scores)),
            f"{mean(o['seconds'] for o in outs):.1f}", f"${mean(o['cost_usd'] for o in outs):.5f}",
        ]) + " |")
        diff_rows.append("| " + lvl + " | " + " | ".join(_pct(mean([s["by_difficulty"][d] for s in scores if s["by_difficulty"][d] is not None] or [0]))
                                                       for d in DIFFICULTIES) + " |")
    reps = {len(r["repeats"]) for r in latest.values()}
    return (f"Repeats per level: {', '.join(map(str, sorted(reps)))}. Fixed / broken are questions per repeat (average). "
            "PASS on wrong, false alarm and PASS is right are per graded round (levels 1 and 3 only).\n\n"
            + "\n".join(rows) + "\n\nRight, by difficulty:\n\n" + "\n".join(diff_rows) + "\n")


def main() -> int:
    parts = ["# 05 · Results\n\nBuilt by `python -m sqlloop.report` from the run files only. Do not edit by hand.\n"
             "Levels: " + ", ".join(NAMES[l] for l in LEVEL_ORDER) + ".\n"]
    for name, title, sub in (("main", "Main set (60 questions, 6 databases)", RUNS_DIR), ("test", "Held-out set (60 questions, 5 other databases)", RUNS_DIR / "test")):
        diff = {str(q.qid): q.difficulty for q in load_set(name)}
        parts.append(f"## {title}\n\n" + build(sub, diff, name))
    parts.append(f"Total spent on this topic (all run files, smoke included): ${spent_in_runs(RUNS_DIR):.2f}\n")
    RESULTS.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
