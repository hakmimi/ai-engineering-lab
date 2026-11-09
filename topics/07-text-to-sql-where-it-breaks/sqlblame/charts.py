"""The blog's graphs as plain SVG, from the run files. Uses topic 04's bar_chart (same look across the series).

    python -m sqlblame.charts      (PYTHONPATH also needs topics/04-agent-security-review-agentdojo)
"""

from __future__ import annotations

import sys
from pathlib import Path

from agentreview.charts import bar_chart
from sqlblame.levels import LEVELS
from sqlblame.paths import RUNS_DIR, TOPIC_DIR
from sqlblame.report import NAMES, _score, latest_files, main_threshold, signal_rows
from sqlblame.signals import signal_rates

CHARTS_DIR = TOPIC_DIR / "charts"
SETS = (("main", "Main set"), ("test", "Held-out set"))


def _pct(v: float) -> str:
    return f"{v:.0%}"


def build_charts(runs_dir: Path, out_dir: Path = CHARTS_DIR) -> list[Path]:
    runs = {s: latest_files(runs_dir, s)[0] for s, _ in SETS}
    if not any(runs.values()):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(name: str, svg: str) -> None:
        (out_dir / name).write_text(svg, encoding="utf-8")
        written.append(out_dir / name)

    series = [(label, cls) for (s, label), cls in zip(SETS, ("s1", "s2"))]
    rows = [[_score(runs[s][lv], "right") if lv in runs[s] else None for s, _ in SETS] for lv in LEVELS]
    save("right-by-level.svg", bar_chart(
        "Right answers by what the writer was shown", "Share of questions whose SQL returns the right rows",
        [("", [NAMES[lv] for lv in LEVELS], rows)], series, 1.0, _pct))

    cats = ["All tables found", "Exact set", "Table overlap", "Picked from another database"]
    keys = ["all_found", "exact", "overlap", "wrong_db"]
    if any("C" in runs[s] for s, _ in SETS):
        vals = [[_score(runs[s]["C"], k) if "C" in runs[s] else None for s, _ in SETS] for k in keys]
        save("table-agent.svg", bar_chart(
            "How the table agent did", "Level C: one call reads all 75 table cards and names the tables",
            [("", cats, vals)], series, 1.0, _pct))

    threshold = main_threshold(runs_dir)
    if threshold is not None:
        sig = {s: signal_rates(signal_rows(runs_dir, s), threshold) for s, _ in SETS}
        names = {"runs": "The query runs", "has_output": "It returns rows", "similarity": "LLM similarity"}
        vals = [[sig[s][k]["good_when_wrong"] for s, _ in SETS] for k in names]
        save("signals.svg", bar_chart(
            'Cheap signals saying "good" to a wrong answer', "Share of wrong final SQL each signal still calls good",
            [("", list(names.values()), vals)], series, 1.0, _pct))
    return written


def main() -> int:
    for p in build_charts(RUNS_DIR):
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
