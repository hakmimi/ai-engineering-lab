"""Build results.md from the run files only.

    python -m sqlblame.report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from sqlblame.levels import LEVELS
from sqlblame.paths import RUNS_DIR, TOPIC_DIR
from sqlblame.run import out_dir_for, spent_in_runs
from sqlblame.signals import pick_threshold, signal_rates

RESULTS = TOPIC_DIR / "results.md"
NAMES = {"A": "A · whole database", "B": "B · right tables", "C": "C · table agent, whole warehouse"}
SET_TITLES = {"main": "Main set (60 questions, 6 databases)", "test": "Held-out set (60 questions, 5 other databases)"}
DASH = "–"


def latest_files(runs_dir: Path, set_name: str) -> tuple[dict[str, dict], dict | None]:
    folder = out_dir_for(runs_dir, set_name, smoke=False)
    runs = {}
    for lv in LEVELS:
        files = sorted(folder.glob(f"level-{lv}-*.json")) if folder.exists() else []
        if files:
            runs[lv] = json.loads(files[-1].read_text(encoding="utf-8"))
    judges = sorted(folder.glob("judge-*.json")) if folder.exists() else []
    return runs, (json.loads(judges[-1].read_text(encoding="utf-8")) if judges else None)


def _avg(values):
    vals = [v for v in values if v is not None]
    return mean(vals) if vals else None


def _pct(v) -> str:
    return DASH if v is None else f"{v:.0%}"


def _score(run: dict, key: str):
    return _avg(r["scores"].get(key) for r in run["repeats"])


def _per_question(run: dict, key: str):
    return _avg(o.get(key, 0.0) for r in run["repeats"] for o in r["results"].values() if not o.get("error"))


def gaps(right: dict) -> dict[str, str]:
    def gap(a, b):
        x, y = right.get(a), right.get(b)
        return DASH if x is None or y is None else f"{round((x - y) * 100):+d}"
    return {"B − A": gap("B", "A"), "B − C": gap("B", "C"), "C − A": gap("C", "A")}


def signal_rows(runs_dir: Path, set_name: str) -> list[dict]:
    runs, judge = latest_files(runs_dir, set_name)
    scores = (judge or {}).get("scores", {})
    rows = []
    for lv, run in runs.items():
        for i, rep in enumerate(run["repeats"]):
            for qid, o in rep["results"].items():
                if o.get("error"):
                    continue
                rows.append({"right": bool(o["right"]), "runs": not o.get("final_error"),
                             "has_output": bool(o.get("n_rows")), "similarity": scores.get(f"{lv}|{i}|{qid}")})
    return rows


def build(runs_dir: Path, set_name: str, threshold: float | None) -> str:
    runs, judge = latest_files(runs_dir, set_name)
    out = [f"## {SET_TITLES[set_name]}", ""]
    if not runs:
        return "\n".join(out + ["No runs yet.", ""])
    reps = {lv: len(r["repeats"]) for lv, r in runs.items()}
    out += [f"Repeats per level: {', '.join(f'{lv} {n}' for lv, n in reps.items())}. Rates are averaged over repeats; "
            "API errors are left out of them and counted.", "",
            "| Level | Right | simple | moderate | challenging | Runs | Has output | $ / question | s / question | API errors |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    right = {}
    for lv in LEVELS:
        run = runs.get(lv)
        if not run:
            out.append(f"| {NAMES[lv]} | {DASH} |" + f" {DASH} |" * 8)
            continue
        right[lv] = _score(run, "right")
        diff = [_avg(r["scores"]["by_difficulty"].get(d) for r in run["repeats"]) for d in ("simple", "moderate", "challenging")]
        cost, secs = _per_question(run, "cost_usd"), _per_question(run, "seconds")
        api = sum(r["scores"]["api_errors"] for r in run["repeats"])
        out.append(f"| {NAMES[lv]} | {_pct(right[lv])} | {' | '.join(_pct(d) for d in diff)} | {_pct(_score(run, 'runs'))} | "
                   f"{_pct(_score(run, 'has_output'))} | ${cost:.5f} | {secs:.1f} | {api} |")
    out += ["", "Gaps, in points of Right:", "", "| Gap | Points | What it shows |", "|---|---|---|"]
    meaning = {"B − A": "what dropping the extra tables is worth", "B − C": "what the table agent's mistakes cost",
               "C − A": "what adding a table agent over the whole warehouse is worth"}
    out += [f"| {k} | {v} | {meaning[k]} |" for k, v in gaps(right).items()]
    if "C" in runs:
        c = runs["C"]
        out += ["", "The table agent (level C), averaged over repeats:", "",
                "| Overlap | All found | Exact | Extra tables | Wrong database | Made-up names | Agent empty | Right when all found | Right when some missing |",
                "|---|---|---|---|---|---|---|---|---|",
                f"| {_pct(_score(c, 'overlap'))} | {_pct(_score(c, 'all_found'))} | {_pct(_score(c, 'exact'))} | "
                f"{_score(c, 'extra'):.2f} | {_pct(_score(c, 'wrong_db'))} | {sum(r['scores']['made_up'] for r in c['repeats'])} | "
                f"{sum(r['scores']['agent_empty'] for r in c['repeats'])} | {_pct(_score(c, 'right_all_found'))} | "
                f"{_pct(_score(c, 'right_missing'))} |"]
    rows = signal_rows(runs_dir, set_name)
    have_judge = judge is not None and threshold is not None
    rates = signal_rates(rows, threshold if have_judge else 1.0)
    out += ["", "Uber's cheap signals against the real answer (every final SQL, all levels and repeats):", ""]
    if have_judge:
        out.append(f"LLM similarity: \"good\" means a score ≥ threshold {threshold}, picked on the main set and used unchanged "
                   f"here. Unreadable scores: {rates['judge_unreadable']}.")
        out.append("")
    out += ["| Signal | Says \"good\" when the answer is wrong | Says \"good\" when it is right |", "|---|---|---|"]
    labels = {"runs": "The query runs", "has_output": "It returns rows", "similarity": "LLM similarity to the golden SQL"}
    for k, label in labels.items():
        if k == "similarity" and not have_judge:
            out.append(f"| {label} | {DASH} | {DASH} |")
            continue
        out.append(f"| {label} | {_pct(rates[k]['good_when_wrong'])} | {_pct(rates[k]['good_when_right'])} |")
    return "\n".join(out + [""])


def main_threshold(runs_dir: Path) -> float | None:
    rows = [r for r in signal_rows(runs_dir, "main") if r["similarity"] is not None]
    return pick_threshold([(r["similarity"], r["right"]) for r in rows]) if rows else None


def main() -> int:
    threshold = main_threshold(RUNS_DIR)
    parts = ["# 07 · Results", "",
             "Built by `python -m sqlblame.report` from the run files only. Do not edit by hand.",
             "Levels: A · the writer gets the whole database, B · only the right tables (Uber's decoupled flow), "
             "C · a table agent picks from all 75 tables first (Uber's vanilla flow).", ""]
    parts += [build(RUNS_DIR, s, threshold) for s in ("main", "test")]
    parts.append(f"Total spent on this topic (all run and judge files, smoke included): ${spent_in_runs(RUNS_DIR):.2f}")
    RESULTS.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
