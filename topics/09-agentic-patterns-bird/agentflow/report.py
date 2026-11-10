"""results.md and charts/*.svg from the run files only (the newest full run per level and set).

    python -m agentflow.report
"""

from __future__ import annotations

import sys
from pathlib import Path

from agentflow.levels import LEVELS
from agentflow.paths import CHARTS_DIR, RUNS_DIR, TOPIC_DIR
from shared.charts import bar_chart, pct
from shared.runs import latest_run

NAMES = {"0": "0 · one prompt", "1": "1 · routing", "1h": "1h · routing + handoff", "2": "2 · parallel vote",
         "3": "3 · orchestrator-worker", "4": "4 · evaluator-optimizer", "5": "5 · free agent"}
SETS = (("main", "Main set", "60 questions, 6 databases"), ("test", "Held-out set", "60 questions, 5 other databases"))
HEAD = ("| Level | Right | Right, lowest–highest repeat | Same answer 3/3 | Right 3/3 | Questions in 3/3 | Right database "
        "| No answer | SQL errors | $ / question | s / question (median) | Calls / question | API errors |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def _avg(run: dict, key: str):
    vals = [r["scores"][key] for r in run["repeats"] if r["scores"].get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _spread(run: dict) -> tuple:
    vals = [r["scores"]["right"] for r in run["repeats"] if r["scores"].get("right") is not None]
    return (min(vals), max(vals)) if vals else (None, None)


def _p(v) -> str:
    return "–" if v is None else f"{v:.0%}"


def level_row(level: str, run: dict | None) -> str:
    if run is None:
        return f"| {NAMES[level]} | not run |" + " |" * 11
    c = run.get("consistency") or {}
    cost, secs, calls = _avg(run, "cost"), _avg(run, "seconds_median") or _avg(run, "seconds"), _avg(run, "calls")
    errors = sum(r["scores"]["api_errors"] for r in run["repeats"])
    lo, hi = _spread(run)
    spread = "–" if lo is None else f"{lo * 100:.0f}–{hi * 100:.0f}%"
    return (f"| {NAMES[level]} | {_p(_avg(run, 'right'))} | {spread} | {_p(c.get('same'))} | {_p(c.get('right_all'))} "
            f"| {c.get('n', '–')} | {_p(_avg(run, 'right_db'))} | {_p(_avg(run, 'no_answer'))} | {_p(_avg(run, 'sql_errors'))} "
            f"| {'–' if cost is None else f'${cost:.5f}'} | {'–' if secs is None else f'{secs:.1f}'} "
            f"| {'–' if calls is None else f'{calls:.1f}'} | {errors} |")


def _detail(level: str, run: dict) -> str | None:
    f = lambda k: _avg(run, k)
    if level == "1h":
        return f"handed to the human {_p(f('handoff'))}; right on the rest {_p(f('right_rest'))}"
    if level == "2" and f("agree") is not None:
        return f"{f('agree'):.1f} of 3 writers agree with the winner"
    if level == "3" and f("n_sub") is not None:
        return f"{f('n_sub'):.1f} sub-questions on average"
    if level == "4" and f("rounds") is not None:
        return f"{f('rounds'):.2f} rounds on average"
    if level == "5" and f("steps") is not None:
        return f"{f('steps'):.1f} steps on average; cap hit {_p(f('cap'))}"
    return None


PATHS = ("answered at once", "described a database first", "ran SQL first")


def agent_paths(run: dict) -> list[tuple[str, int, int, int]]:
    """The free agent's answers over all repeats, split by what it looked at before answering:
    (path, answers, right, SQL errors). API errors are left out."""
    counts = {p: [0, 0, 0] for p in PATHS}
    for rep in run["repeats"]:
        for r in rep["results"].values():
            if r.get("error"):
                continue
            tools = {t.get("tool") for t in r.get("trace") or []}
            path = PATHS[2] if "run_sql" in tools else PATHS[1] if "describe" in tools else PATHS[0]
            c = counts[path]
            c[0], c[1], c[2] = c[0] + 1, c[1] + bool(r.get("right")), c[2] + bool(r.get("final_error"))
    return [(p, *counts[p]) for p in PATHS if counts[p][0]]


def latest_runs(runs_dir: Path, set_name: str) -> dict:
    return {lv: latest_run(runs_dir, set_name, lv) for lv in LEVELS}


def build_results(runs_dir: Path, whatif: dict | None = None) -> str:
    """whatif: set -> agentflow.whatif.prefix_whatif(...) for level 5, shown as a labelled line."""
    by_set = {s: latest_runs(runs_dir, s) for s, _, _ in SETS}
    models = sorted({r["model"] for runs in by_set.values() for r in runs.values() if r})
    out = ["# 09 · Results", "",
           "Built by `python -m agentflow.report` from the run files only. Do not edit by hand.",
           f"Model: {', '.join(models) or '–'}. Right = the final query runs on the question's own database and returns "
           "the gold rows (order and duplicates ignored). Same answer 3/3 = all repeats end the same way (same "
           "database and rows, or the same failure). Rates are averaged over repeats; API errors are left out of "
           "them and counted.", ""]
    for set_name, title, what in SETS:
        runs = by_set[set_name]
        out += [f"## {title} ({what})", ""]
        if not any(runs.values()):
            out += ["No full run yet.", ""]
            continue
        reps = ", ".join(f"{lv} {len(r['repeats'])}" for lv, r in runs.items() if r)
        out += [f"Repeats per level: {reps}.", "", HEAD] + [level_row(lv, runs[lv]) for lv in LEVELS] + [""]
        moves = [(hi - lo, lv) for lv, r in runs.items() if r and len(r["repeats"]) > 1 for lo, hi in [_spread(r)]
                 if lo is not None]
        if moves:
            move, lv = max(moves)
            out += [f"Noise floor: one question is {100 / 60:.1f} points. Repeats of the same level moved by up to "
                    f"{move * 100:.0f} points (level {lv}), so smaller gaps between levels are not clear effects.", ""]
        details = [(lv, _detail(lv, r)) for lv, r in runs.items() if r]
        details = [(lv, d) for lv, d in details if d]
        if details:
            out += ["| Level | Inside the pattern |", "|---|---|"] + [f"| {NAMES[lv]} | {d} |" for lv, d in details] + [""]
        five = runs.get("5")
        paths = agent_paths(five) if five else []
        if paths:
            total = sum(n for _, n, _, _ in paths)
            out += ["How the free agent worked (all repeats; API errors left out):", "",
                    "| Before answering, it | Answers | Right | SQL errors |", "|---|---|---|---|"]
            out += [f"| {p} | {n} of {total} ({n / total:.0%}) | {r / n:.0%} | {e / n:.0%} |" for p, n, r, e in paths]
            out.append("")
        w = (whatif or {}).get(set_name)
        if five and w and w.get("right") is not None:
            out += [f"What if the agent's `database.table` names had worked (offline rerun of its stored queries): "
                    f"{w['prefix_failures']} answers failed on the prefix"
                    + (f" (the agent had run {w['run_before']} of these queries before answering)"
                       if w.get("run_before") is not None else "")
                    + f", {w['fixed']} of them would be right; "
                    f"right would be {_p(w['right'])} instead of {_p(_avg(five, 'right'))}"
                    + (f", same answer 3/3 {_p(w['same'])} instead of {_p((five.get('consistency') or {}).get('same'))}"
                       if w.get("same") is not None else "") + ".", ""]
        if five:
            r5, s5 = _avg(five, "right"), (five.get("consistency") or {}).get("same")
            gap = lambda a, b: "–" if a is None or b is None else f"{(a - b) * 100:+.0f}"
            out += ["Workflow minus the free agent (level 5), in points:", "",
                    "| Level | Right | Same answer 3/3 |", "|---|---|---|"]
            for lv in LEVELS[:-1]:
                if runs[lv]:
                    name = NAMES[lv] + (" (a person helps)" if lv == "1h" else "")
                    out.append(f"| {name} | {gap(_avg(runs[lv], 'right'), r5)} "
                               f"| {gap((runs[lv].get('consistency') or {}).get('same'), s5)} |")
            out.append("")
    return "\n".join(out)


def build_charts(runs_dir: Path, out_dir: Path = CHARTS_DIR) -> list[Path]:
    runs = {s: latest_runs(runs_dir, s) for s, _, _ in SETS}
    if not any(r for by_level in runs.values() for r in by_level.values()):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    series = [(title, cls) for (_, title, _), cls in zip(SETS, ("s1", "s2"))]
    cats = [NAMES[lv] for lv in LEVELS]

    def vals(get):
        return [[get(runs[s][lv]) if runs[s][lv] else None for s, _, _ in SETS] for lv in LEVELS]

    def biggest(rows):
        return max([v for row in rows for v in row if v is not None] or [1.0])

    same = lambda r: (r.get("consistency") or {}).get("same")
    secs, cost = vals(lambda r: _avg(r, "seconds_median") or _avg(r, "seconds")), vals(lambda r: _avg(r, "cost"))
    charts = {
        "right-by-level.svg": bar_chart("Right answers by pattern", "Share of questions whose final SQL returns the gold rows",
                                        [("", cats, vals(lambda r: _avg(r, "right")))], series, 1.0, pct),
        "same-answer.svg": bar_chart("Same answer in all 3 runs", "Share of questions where the 3 repeats ended the same way",
                                     [("", cats, vals(same))], series, 1.0, pct),
        "seconds.svg": bar_chart("Time per question", "Median wall-clock seconds; parallel calls overlap",
                                 [("", cats, secs)], series, biggest(secs) * 1.1, lambda v: f"{v:.1f} s"),
        "cost.svg": bar_chart("Cost per question", "US dollars at list prices",
                              [("", cats, cost)], series, biggest(cost) * 1.1, lambda v: f"${v:.4f}"),
    }
    written = []
    for name, svg in charts.items():
        (out_dir / name).write_text(svg, encoding="utf-8")
        written.append(out_dir / name)
    return written


def agent_whatif(runs_dir: Path) -> dict:
    """The offline prefix rerun for each set's newest level-5 run (reads the BIRD databases, no model calls)."""
    from agentflow.run import gold_rows
    from agentflow.whatif import prefix_whatif
    from sqlloop.data import db_path, load_set

    out = {}
    for set_name, _, _ in SETS:
        run = latest_run(runs_dir, set_name, "5")
        if run:
            questions = load_set(set_name)
            gold, _ = gold_rows(questions)
            out[set_name] = prefix_whatif(run, gold, {str(q.qid): q.db_id for q in questions}, path_of=db_path)
    return out


def main() -> int:
    (TOPIC_DIR / "results.md").write_text(build_results(RUNS_DIR, agent_whatif(RUNS_DIR)), encoding="utf-8")
    print(f"Wrote {TOPIC_DIR / 'results.md'}")
    for p in build_charts(RUNS_DIR):
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
