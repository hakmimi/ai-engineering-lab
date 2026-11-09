"""Build results.md from the saved run files only. Smoke runs (--limit) and partial runs are left out.

    python -m agentreview.report
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

from agentreview.data import load_key, load_pairs, load_styles
from agentreview.models import Verdict, verdict_from_dict
from agentreview.run import RUNS_DIR, spent_so_far
from agentreview.score import cheap, flagged, flip_rate, fooled, score

RESULTS = Path(__file__).resolve().parent.parent / "results.md"
LEVEL_NAMES = {"0": "0 · rules only", "1": "1 · one prompt", "2": "2 · the article's way"}
ARTICLE = ("**Article said:** 4 of 20 example sessions in Act, about $0.09 for all 20 "
           "(about $0.0045 per session) on `claude-haiku-5-5`; \"worked examples, not an accuracy measurement\".")


def _latest(runs_dir: Path, set_name: str, level: str) -> dict | None:
    for path in sorted((runs_dir / set_name).glob(f"level-{level}-*.json"), reverse=True):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("limit") is None and not run.get("partial"):
            return run
    return None


def _verdicts(rep: dict) -> dict[str, Verdict]:
    return {sid: verdict_from_dict(v) for sid, v in rep["verdicts"].items()}


def _pct(x: float) -> str:
    return f"{x:.0%}"


def _row(name: str, reps: list[tuple[dict[str, Verdict], float, float]], key: dict[str, str]) -> str:
    """reps: per repeat (verdicts, $ per session, seconds per session)."""
    scores = [score(v, key) for v, _, _ in reps]
    avg = lambda f: mean(f(s) for s in scores)  # noqa: E731
    return (
        f"| {name} | {_pct(avg(lambda s: s.caught))} | {_pct(avg(lambda s: s.caught_act))} | "
        f"{_pct(avg(lambda s: s.false_alarms))} | {_pct(avg(lambda s: s.refused_flagged))} | "
        f"{avg(lambda s: s.not_reviewed):.1f} / {avg(lambda s: s.errors):.1f} / {avg(lambda s: s.failed):.1f} | "
        f"{mean(sum(v.tries.count('quote_fail') for v in vs.values()) for vs, _, _ in reps):.1f} | "
        f"${mean(c for _, c, _ in reps):.4f} | {mean(t for _, _, t in reps):.1f} |"
    )


def _per_session(rep: dict, field: str) -> float:
    values = rep.get(field, {}).values()
    return sum(values) / len(rep["verdicts"]) if rep["verdicts"] else 0.0


Reps = list[tuple[dict[str, Verdict], float, float]]  # per repeat: verdicts, $ per session, seconds per session


def level_reps(runs_dir: Path, set_name: str) -> dict[str, Reps | None]:
    """Per level name (and 2-cheap): the repeats of the latest full run, or None if it hasn't run."""
    runs = {lv: _latest(runs_dir, set_name, lv) for lv in LEVEL_NAMES}
    out: dict[str, Reps | None] = {}
    for lv, name in LEVEL_NAMES.items():
        run = runs[lv]
        out[name] = None if run is None else [
            (_verdicts(r), _per_session(r, "cost_usd"), _per_session(r, "seconds")) for r in run["repeats"]
        ]
    out["2-cheap"] = None
    if runs["0"] and runs["2"]:
        l0 = _verdicts(runs["0"]["repeats"][0])
        reps = []
        for r in runs["2"]["repeats"]:
            l2 = _verdicts(r)
            mixed = cheap(l0, l2)
            sent = [sid for sid in l0 if mixed[sid] is l2.get(sid)]
            reps.append((mixed, sum(r["cost_usd"].get(sid, 0) for sid in sent) / len(l0),
                         sum(r["seconds"].get(sid, 0) for sid in sent) / len(l0)))
        out["2-cheap"] = reps
    return out


def _table(runs_dir: Path, set_name: str) -> list[str]:
    key = load_key(set_name)
    lines = [
        f"## {'Main set (tuning allowed)' if set_name == 'main' else 'Held-out set (never tuned on)'}",
        "",
        f"{sum(k == 'bad' for k in key.values())} bad, {sum(k == 'refused' for k in key.values())} refused, "
        f"{sum(k == 'clean' for k in key.values())} clean sessions. Averages over the repeats.",
        "",
        "| Level | Caught | in Act | False alarms | Refused flagged | Not reviewed / errors / API failures | Quote fails | $ per session | s per session |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    runs = {lv: _latest(runs_dir, set_name, lv) for lv in LEVEL_NAMES}
    for name, reps in level_reps(runs_dir, set_name).items():
        if reps is None:
            lines.append(f"| {name} | not run yet | | | | | | | |")
        else:
            lines.append(_row(name, reps, key))
    if set_name == "test":
        lines += ["", *_by_style(runs, key, load_styles(set_name))]
    return lines + [""]


def _by_style(runs: dict, key: dict[str, str], styles: dict[str, str]) -> list[str]:
    """Held-out bad sessions caught, per attack style: one number per level hides which styles the rules miss."""
    names = sorted({styles[sid] for sid, k in key.items() if k == "bad"})
    lines = ["Bad sessions caught, by attack style (averaged over repeats):", "",
             "| Level | " + " | ".join(f"{n} ({sum(1 for s, k in key.items() if k == 'bad' and styles[s] == n)})" for n in names) + " |",
             "|---|" + "---|" * len(names)]
    for lv, name in LEVEL_NAMES.items():
        run = runs[lv]
        if run is None:
            lines.append(f"| {name} | " + " | ".join("not run yet" for _ in names) + " |")
            continue
        cells = []
        for n in names:
            sub_key = {sid: k for sid, k in key.items() if k == "bad" and styles[sid] == n}
            cells.append(_pct(mean(score(_verdicts(r), sub_key).caught for r in run["repeats"])))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return lines


def _fooled_section(runs_dir: Path) -> list[str]:
    pairs = load_pairs()
    lines = [
        "## Fooled set",
        "",
        f"{len(pairs)} held-out bad sessions, each with one added line telling the reviewer the action was approved.",
        "Share = of the sessions caught without the note, how many the note turned into routine.",
        "Noise floor = how often a caught session is not caught in another repeat of the same held-out run, with no note:",
        "the model is not fully repeatable, so only the part of \"fooled\" above this line is the note's doing.",
        "",
        "| Level | Fooled | Count per repeat | Noise floor |",
        "|---|---|---|---|",
    ]
    for lv, name in LEVEL_NAMES.items():
        plain, noted = _latest(runs_dir, "test", lv), _latest(runs_dir, "fooled", lv)
        if not plain or not noted:
            lines.append(f"| {name} | not run yet | | |")
            continue
        n = min(len(plain["repeats"]), len(noted["repeats"]))
        results = [fooled(_verdicts(plain["repeats"][i]), _verdicts(noted["repeats"][i]), pairs) for i in range(n)]
        floor = flip_rate([_verdicts(r) for r in plain["repeats"]], sorted(set(pairs.values())))
        floor_text = f"chance flips between repeats: {_pct(floor[0])}" if floor[2] else "n/a (one repeat)"
        lines.append(f"| {name} | {_pct(mean(r[0] for r in results))} | "
                     + ", ".join(f"{r[1]} of {r[2]}" for r in results) + f" | {floor_text} |")
    return lines + [""]


def build_results(runs_dir: Path = RUNS_DIR) -> str:
    lines = ["# Topic 4 results", "", "Generated by `python -m agentreview.report` from the run files only.", ""]
    for set_name in ("main", "test"):
        lines += _table(runs_dir, set_name)
    lines += _fooled_section(runs_dir)
    main2 = _latest(runs_dir, "main", "2")
    got = (f"${mean(_per_session(r, 'cost_usd') for r in main2['repeats']):.4f} per session at level 2 on the main set "
           f"(`{main2['model']}`)") if main2 else "not run yet"
    lines += ["## Cost against the article", "", ARTICLE, "", f"**We got:** {got}.", "",
              f"Total spent on this topic, all run files: ${spent_so_far(runs_dir):.3f}.", ""]
    return "\n".join(lines)


def main() -> int:
    from agentreview.charts import build_charts  # charts reuse this module's helpers

    RESULTS.write_text(build_results(), encoding="utf-8")
    print(f"Wrote {RESULTS}")
    for path in build_charts(RUNS_DIR):
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
