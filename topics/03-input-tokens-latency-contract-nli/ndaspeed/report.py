"""Write results.md from the run files only: one section per test, from its latest run.

Warm-up calls, pre-warm calls and failed attempts are left out of every statistic and counted as errors where they failed.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from ndaspeed.config import RESULTS, RUNS_DIR, SEED
from ndaspeed.cost import cost_of, spent_in_runs
from ndaspeed.stats import bootstrap_diff, median, p90, slope_per_100k, values
from ndaspeed.timer import Timing

NOT_STATS = {"warmup", "prewarm_call", "error"}
TITLES = {"0": "Network floor", "1": "Prompt size and first word", "2": "Caching: cache-friendly vs cache-busting prompts",
          "3": "Pre-warming", "4": "Server-side conversation (previous_response_id)"}
ARTICLE = {
    "0": "about 0.4–0.5 s to the first word for a tiny prompt (Claude, Anthropic's network).",
    "1": "about +0.25 s per 100K uncached input tokens (Haiku 5.5: 0.50 / 0.76 / 1.02 s at ~17K / 100K / 200K), "
         "about the same on every model.",
    "2": "caching cuts cost ~85%; on short tasks speed does not change; with a ~146K prefix, turn 2 went 1.7 s → 0.5 s.",
    "3": "with a 146K prompt, the first turn went 1.0 s → 0.8 s after a pre-warm request.",
    "4": "with 16 page images, the first word went 1.27 s → 0.63 s and the request 22.3 MB → 0.3 KB.",
}
HOW_TO_RUN = """\
## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/02-prompt-vs-workflow-contract-nli;topics/03-input-tokens-latency-contract-nli"
.venv\\Scripts\\python -m ndaspeed.run --test 1 --dry-run           # cost estimate only
.venv\\Scripts\\python -m ndaspeed.run --test 1 --model both --yes  # tests 0-4, one at a time
.venv\\Scripts\\python -m ndaspeed.report                           # rewrites this file
```
"""


# ---------------------------------------------------------------- helpers
def _f(x: float | None) -> str:
    return "–" if x is None else f"{x:.2f}"


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _latest_runs(runs_dir: Path) -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}
    if not runs_dir.exists():
        return out
    for p in sorted(runs_dir.glob("test*.json")):  # names carry the time, so later files sort last
        run = json.loads(p.read_text(encoding="utf-8"))
        out[run["test"]] = (p.name, run)
    return out


def _measured(run: dict, variant: str | None = None) -> list[dict]:
    return [r for r in run["records"] if r["variant"] not in NOT_STATS and "skipped" not in r
            and not r["timing"]["error"] and (variant is None or r["variant"] == variant)]


def _errors(records: list[dict]) -> int:
    return sum(1 for r in records if "timing" in r and r["variant"] != "prewarm_call" and r["timing"]["error"]) + \
        sum(1 for r in records if r["variant"] not in NOT_STATS and r.get("label") == "error" and not r["timing"]["error"])


def _ft(recs: list[dict]) -> list[float | None]:
    return [r["timing"]["first_text_s"] for r in recs]


def _label_right(recs: list[dict]) -> float | None:
    judged = [r for r in recs if "key_label" in r]
    return sum(r["label"] == r["key_label"] for r in judged) / len(judged) if judged else None


def _evidence_found(recs: list[dict]) -> float | None:
    found = total = 0
    for r in recs:
        if r.get("key_label") in ("entailment", "contradiction"):
            total += len(r["key_evidence"])
            found += len(set(r["key_evidence"]) & set(r["evidence"]))
    return found / total if total else None


def _really_cold(recs: list[dict]) -> list[dict]:
    """A request meant to be cold that still read from cache is not cold: it stays out of the stats."""
    return [r for r in recs if r["timing"]["cached_tokens"] == 0]


def _cold_check(recs: list[dict]) -> str:
    n = sum(1 for r in recs if r["timing"]["cached_tokens"] > 0)
    return f"Cold check: {n} request(s) with cached tokens > 0" + (" (good: none read from cache)" if n == 0 else
                                                                    " — not really cold, so left out of the stats")


def _no_text(recs: list[dict]) -> str:
    return f"No answer text: {sum(1 for r in recs if r['timing']['first_text_s'] is None)} request(s) (left out of first-word stats)"


def _interval(a: list, b: list, label: str) -> str:
    if len(values(a)) < 2 or len(values(b)) < 2:
        return ""
    low, high = bootstrap_diff(a, b, random.Random(SEED))
    return f"{label}: difference of medians, 95% interval [{low:+.2f}, {high:+.2f}] s (an interval that excludes 0 is a real difference)."


# ---------------------------------------------------------------- sections
def _test0(run: dict) -> list[str]:
    m = _measured(run)
    return [f"We got: first word p50 {_f(median(_ft(m)))} s on {', '.join(run['models'].values())} (home connection).", "",
            "| First word p50 | p90 | min | Total p50 | n | errors |", "|---|---|---|---|---|---|",
            f"| {_f(median(_ft(m)))} | {_f(p90(_ft(m)))} | {_f(min(values(_ft(m)), default=None))} | "
            f"{_f(median([r['timing']['total_s'] for r in m]))} | {len(m)} | {_errors(run['records'])} |", "",
            f"- {_no_text(m)}"]


def _test1(run: dict) -> list[str]:
    all_cold = _measured(run, "cold")
    m = _really_cold(all_cold)
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in m:
        groups[(r["model"], r["size"])].append(r)
    lines = ["| Model | Target size | Input tokens p50 | First word p50 | p90 | n |", "|---|---|---|---|---|---|"]
    for (model, size), recs in sorted(groups.items()):
        lines.append(f"| {model} | {size:,} | {median([r['timing']['input_tokens'] for r in recs]):,.0f} | "
                     f"{_f(median(_ft(recs)))} | {_f(p90(_ft(recs)))} | {len(recs)} |")
    slopes = []
    for model in sorted({r["model"] for r in m}):
        pts = [(r["timing"]["input_tokens"], r["timing"]["first_text_s"]) for r in m
               if r["model"] == model and r["timing"]["first_text_s"] is not None]
        if len({x for x, _ in pts}) >= 2:
            slopes.append(f"Slope, {model}: {slope_per_100k([x for x, _ in pts], [y for _, y in pts]):+.2f} s per 100K input tokens")
    skipped = [f"Skipped: size {r['size']:,} — {r['skipped']}" for r in run["records"] if "skipped" in r]
    return ["We got: " + ("; ".join(slopes) if slopes else "no slope (too few sizes)") + ".", "", *lines, "",
            *[f"- {s}" for s in slopes + skipped], f"- {_cold_check(all_cold)}", f"- {_no_text(all_cold)}",
            f"- Errors: {_errors(run['records'])}"]


def _chat_rows(run: dict, variants: tuple[str, ...]) -> tuple[list[str], dict]:
    rows, later_by = [], {}
    for pack in ("short", "long"):
        for v in variants:
            recs = [r for r in _measured(run, v) if r.get("pack") == pack]
            if v == "cache_off":
                recs = _really_cold(recs)  # cache-busting turns must not read from cache
            if v == "thread":
                recs = [r for r in recs if not r.get("fallback")]  # a fallback turn is a full re-send
            if not recs:
                continue
            later = [r for r in recs if r["turn"] >= 1]
            later_by[(pack, v)] = _ft(later)
            tin = sum(r["timing"]["input_tokens"] for r in recs)
            cached = sum(r["timing"]["cached_tokens"] for r in recs)
            chats = len({r["chat"] for r in recs})
            usd = sum(cost_of(Timing(**r["timing"]), r["model"]) for r in recs) / chats
            all_v = [r for r in run["records"] if r.get("pack") == pack and r["variant"] == v]
            rows.append(f"| {pack} | {v} | {_f(median(_ft([r for r in recs if r['turn'] == 0])))} | {_f(median(_ft(later)))} | "
                        f"{_f(median([r['timing']['total_s'] for r in recs]))} | {_pct(cached / tin if tin else None)} | "
                        f"${usd:.4f} | {_pct(_label_right(recs))} | {_pct(_evidence_found(recs))} | {_errors(all_v)} |")
    return rows, later_by


def _test2(run: dict) -> list[str]:
    rows, later = _chat_rows(run, ("cache_on", "cache_off"))
    notes = [_interval(later.get((p, "cache_off"), []), later.get((p, "cache_on"), []), f"{p} pack, turns 2–17, on − off")
             for p in ("short", "long")]
    got = [f"{p} pack turns 2–17 first word {_f(median(later.get((p, 'cache_off'), [])))} s off → "
           f"{_f(median(later.get((p, 'cache_on'), [])))} s on" for p in ("short", "long")]
    off = [r for r in _measured(run, "cache_off")]
    return ["We got: " + "; ".join(got) + ".", "",
            "| Pack | Variant | First word, turn 1 | First word, turns 2–17 | Total p50 | Cached share | $ per chat "
            "| Label right | Evidence found | Errors |", "|---|---|---|---|---|---|---|---|---|---|", *rows, "",
            *[f"- {n}" for n in notes if n], f"- cache_off {_cold_check(off)}"]


def _test3(run: dict) -> list[str]:
    all_cold, warm = _measured(run, "cold"), _measured(run, "prewarm")
    cold = _really_cold(all_cold)
    hits = sum(1 for r in warm if r["timing"]["cached_tokens"] > 0)
    rows = [f"| {name} | {_f(median(_ft(recs)))} | {_f(p90(_ft(recs)))} | {len(recs)} | {_pct(_label_right(recs))} |"
            for name, recs in (("cold", cold), ("prewarm", warm))]
    note = _interval(_ft(cold), _ft(warm), "prewarm − cold")
    return [f"We got: first question's first word {_f(median(_ft(cold)))} s cold → {_f(median(_ft(warm)))} s pre-warmed.", "",
            "| Variant | First word p50 | p90 | n | Label right |", "|---|---|---|---|---|", *rows, "",
            f"- Warm-up hit rate: {hits}/{len(warm)} pre-warmed questions read the pack from cache",
            f"- {_cold_check(all_cold)}", *([f"- {note}"] if note else []), f"- Errors: {_errors(run['records'])}"]


def _test4(run: dict) -> list[str]:
    rows = []
    for v in ("cache_on", "thread"):
        recs = _measured(run, v)
        later = [r for r in recs if r["turn"] >= 1 and not r.get("fallback")]  # a fallback is a full re-send
        all_v = [r for r in run["records"] if r["variant"] == v]
        rows.append(f"| {v} | {median([r['timing']['request_bytes'] for r in later]) or 0:,.0f} | {_f(median(_ft(later)))} | "
                    f"{sum(1 for r in recs if r.get('fallback'))} | {_pct(_label_right(recs))} | {_errors(all_v)} |")
    on = _ft([r for r in _measured(run, "cache_on") if r["turn"] >= 1])
    th = _ft([r for r in _measured(run, "thread") if r["turn"] >= 1 and not r.get("fallback")])
    note = _interval(on, th, "turns 2–17, thread − re-send")
    return [f"We got: turns 2–17 first word {_f(median(on))} s re-sending everything → {_f(median(th))} s with previous_response_id.",
            "", "| Variant | Request bytes p50 (turns 2–17) | First word p50 (turns 2–17) | Fallbacks | Label right | Errors |",
            "|---|---|---|---|---|---|", *rows, *(["", f"- {note}"] if note else [])]


SECTIONS = {"0": _test0, "1": _test1, "2": _test2, "3": _test3, "4": _test4}


def build_results(runs_dir: Path = RUNS_DIR) -> str:
    latest = _latest_runs(runs_dir)
    out = ["# Results", "", "Generated by `python -m ndaspeed.report` from the run files in `runs/`. "
           "Times are seconds, measured from a home connection; p90 with 5–10 runs is close to the slowest run.", ""]
    for test in "01234":
        out += [f"## Test {test} — {TITLES[test]}", "", f"Article said: {ARTICLE[test]}", ""]
        if test not in latest:
            out += ["Not run yet.", ""]
            continue
        name, run = latest[test]
        out += SECTIONS[test](run) + ["", f"Run file: `{name}` (started {run['started']}"
                                      + (", stopped by the budget" if run.get("stopped") else "") + ")", ""]
    out += ["## Spend", "", "| Run file | $ |", "|---|---|"]
    for p in sorted(runs_dir.glob("test*.json")) if runs_dir.exists() else []:
        spent = json.loads(p.read_text(encoding="utf-8")).get("spent_usd", 0.0)
        out.append(f"| {p.name} | {spent:.4f} |")
    out += ["", f"Total spent: ${spent_in_runs(runs_dir):.2f} (smoke runs in `runs/smoke/` included)", "", HOW_TO_RUN]
    return "\n".join(out)


def main() -> int:
    RESULTS.write_text(build_results(), encoding="utf-8")
    print(f"Wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
