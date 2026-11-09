"""The blog's graphs, as plain SVG files built from the run files (no plotting library needed).

Horizontal bars, thin, square at the baseline and rounded at the data end; every bar carries its value;
a legend for two or more series; light and dark colours from the validated reference palette.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from statistics import mean

from agentreview.data import load_key, load_pairs, load_styles
from agentreview.report import LEVEL_NAMES, _latest, _verdicts, level_reps
from agentreview.score import flip_rate, fooled, score

CHARTS_DIR = Path(__file__).resolve().parent.parent / "charts"
ARTICLE_USD_PER_SESSION = 0.09 / 20

# Reference palette (dataviz skill): slots 1-3 validated together, light and dark. "muted" is for a reference series.
LIGHT = {"s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "muted": "#898781",
         "ink": "#0b0b0b", "ink2": "#52514e", "axis": "#c3c2b7", "grid": "#e1e0d9"}
DARK = {"s1": "#3987e5", "s2": "#d95926", "s3": "#199e70", "muted": "#898781",
        "ink": "#f0efec", "ink2": "#c3c2b7", "axis": "#383835", "grid": "#2c2c2a"}

WIDTH = 720
LABEL_W = 170  # room for category names
PLOT_W = 440
BAR_H = 14
BAR_GAP = 2
GROUP_GAP = 14
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _style() -> str:
    def rules(c: dict) -> str:
        return " ".join(
            [f".{k}{{fill:{v}}}" for k, v in c.items() if k.startswith("s") or k == "muted"]
            + [f".ink{{fill:{c['ink']}}}", f".ink2{{fill:{c['ink2']}}}",
               f".axis{{stroke:{c['axis']}}}", f".grid{{stroke:{c['grid']}}}", f".ref{{stroke:{c['ink2']}}}"]
        )
    return (f"<style>text{{font-family:{FONT};font-variant-numeric:tabular-nums}} {rules(LIGHT)} "
            f"@media (prefers-color-scheme: dark) {{ {rules(DARK)} }}</style>")


def _bar(x0: float, y: float, w: float, cls: str, tip: str) -> str:
    """Square at the baseline (left), 4px rounded at the data end (right)."""
    if w <= 0:
        return f'<rect x="{x0}" y="{y}" width="1" height="{BAR_H}" class="{cls}"><title>{escape(tip)}</title></rect>'
    r = min(4, w / 2, BAR_H / 2)
    d = (f"M{x0},{y} H{x0 + w - r} A{r},{r} 0 0 1 {x0 + w},{y + r} V{y + BAR_H - r} "
         f"A{r},{r} 0 0 1 {x0 + w - r},{y + BAR_H} H{x0} Z")
    return f'<path d="{d}" class="{cls}"><title>{escape(tip)}</title></path>'


def bar_chart(title: str, subtitle: str, panels: list[tuple[str, list[str], list[list[float | None]]]],
              series: list[tuple[str, str]], xmax: float, fmt, ref: tuple[float, str] | None = None) -> str:
    """panels: (panel title, category names, values[category][series]); series: (name, colour class)."""
    out, y = [], 64
    if len(series) > 1:  # legend, top left, under the subtitle
        x = 0
        for name, cls in series:
            out.append(f'<rect x="{x}" y="{y - 10}" width="10" height="10" rx="2" class="{cls}"/>'
                       f'<text x="{x + 16}" y="{y}" font-size="13" class="ink2">{escape(name)}</text>')
            x += 26 + 8 * len(name)
        y += 22
    for p_title, cats, values in panels:
        if p_title:
            out.append(f'<text x="0" y="{y + 12}" font-size="14" font-weight="600" class="ink">{escape(p_title)}</text>')
            y += 24
        top = y
        for cat, vals in zip(cats, values):
            group_h = len(series) * BAR_H + (len(series) - 1) * BAR_GAP
            out.append(f'<text x="{LABEL_W - 10}" y="{y + group_h / 2 + 4}" font-size="13" text-anchor="end" '
                       f'class="ink">{escape(cat)}</text>')
            for (name, cls), v in zip(series, vals):
                if v is None:
                    out.append(f'<text x="{LABEL_W + 4}" y="{y + 11}" font-size="12" class="ink2">not run</text>')
                else:
                    w = PLOT_W * min(v, xmax) / xmax
                    out.append(_bar(LABEL_W, y, w, cls, f"{cat} · {name}: {fmt(v)}"))
                    out.append(f'<text x="{LABEL_W + w + 6}" y="{y + 11}" font-size="12" class="ink2">{escape(fmt(v))}</text>')
                y += BAR_H + BAR_GAP
            y += GROUP_GAP - BAR_GAP
        out.append(f'<line x1="{LABEL_W}" y1="{top - 4}" x2="{LABEL_W}" y2="{y - GROUP_GAP + 4}" class="axis" stroke-width="1"/>')
        if ref is not None:
            rx = LABEL_W + PLOT_W * min(ref[0], xmax) / xmax
            out.append(f'<line x1="{rx}" y1="{top - 6}" x2="{rx}" y2="{y - GROUP_GAP + 6}" class="ref" '
                       f'stroke-width="1.5" stroke-dasharray="4 3"/>'
                       f'<text x="{rx}" y="{y - GROUP_GAP + 22}" font-size="12" text-anchor="middle" class="ink2">'
                       f'{escape(ref[1])}</text>')
            y += 18
        y += 16
    height = y + 4
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
            f'role="img" aria-label="{escape(title)}">{_style()}'
            f'<text x="0" y="22" font-size="18" font-weight="700" class="ink">{escape(title)}</text>'
            f'<text x="0" y="42" font-size="13" class="ink2">{escape(subtitle)}</text>')
    return head + "".join(out) + "</svg>\n"


def _pct(v: float) -> str:
    return f"{v:.0%}"


def _avg(reps, key: dict[str, str], field: str) -> float:
    return mean(getattr(score(v, key), field) for v, _, _ in reps)


def build_charts(runs_dir: Path, out_dir: Path = CHARTS_DIR) -> list[Path]:
    """Write the charts that have data; return their paths. A chart with no run behind it is not written."""
    sets = {s: level_reps(runs_dir, s) for s in ("main", "test")}
    if not any(r for reps in sets.values() for r in reps.values()):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(name: str, svg: str) -> None:
        path = out_dir / name
        path.write_text(svg, encoding="utf-8")
        written.append(path)

    # 1 · caught vs false alarms, main and held-out
    panels = []
    for set_name, label in (("main", "Main set (tuning allowed)"), ("test", "Held-out set (never tuned on)")):
        key, reps = load_key(set_name), sets[set_name]
        names = [n for n, r in reps.items() if r]
        panels.append((label, names, [[_avg(reps[n], key, "caught"), _avg(reps[n], key, "false_alarms")] for n in names]))
    save("caught-vs-false-alarms.svg", bar_chart(
        "Caught vs. false alarms", "Share of bad sessions flagged, and of clean sessions flagged for nothing",
        panels, [("Caught (bad sessions flagged)", "s1"), ("False alarms (clean sessions flagged)", "s2")], 1.0, _pct))

    # 2 · held-out bad sessions caught, by attack style
    key, styles = load_key("test"), load_styles("test")
    names = sorted({styles[s] for s, k in key.items() if k == "bad"})
    lv_series = [(n, c) for n, c in zip(LEVEL_NAMES.values(), ("s1", "s2", "s3"))]
    rows = []
    for st in names:
        sub = {s: k for s, k in key.items() if k == "bad" and styles[s] == st}
        rows.append([_avg(sets["test"][n], sub, "caught") if sets["test"][n] else None for n, _ in lv_series])
    counts = {st: sum(1 for s, k in key.items() if k == "bad" and styles[s] == st) for st in names}
    save("caught-by-style.svg", bar_chart(
        "Held-out: caught by attack style", "Share of bad sessions flagged, per attack style the rules never saw",
        [("", [f"{st} ({counts[st]})" for st in names], rows)], lv_series, 1.0, _pct))

    # 3 · fooled, with the chance noise floor
    pairs, cats, rows = load_pairs(), [], []
    for lv, name in LEVEL_NAMES.items():
        plain, noted = _latest(runs_dir, "test", lv), _latest(runs_dir, "fooled", lv)
        if not plain or not noted:
            continue
        n = min(len(plain["repeats"]), len(noted["repeats"]))
        share = mean(fooled(_verdicts(plain["repeats"][i]), _verdicts(noted["repeats"][i]), pairs)[0] for i in range(n))
        floor = flip_rate([_verdicts(r) for r in plain["repeats"]], sorted(set(pairs.values())))[0]
        cats.append(name)
        rows.append([share, floor])
    if cats:
        save("fooled.svg", bar_chart(
            "Fooled by one planted line", 'Of the bad sessions caught without the note, the share the note turned into "Routine"',
            [("", cats, rows)], [('Fooled by the note', "s1"), ("Flips by chance (no note)", "muted")], 1.0, _pct))

    # 4 · cost per session, main set, against the article
    reps = sets["main"]
    names = [n for n, r in reps.items() if r and n != LEVEL_NAMES["0"]]
    if names:
        costs = [[mean(c for _, c, _ in reps[n])] for n in names]
        top = max([c[0] for c in costs] + [ARTICLE_USD_PER_SESSION]) * 1.25
        save("cost-per-session.svg", bar_chart(
            "Cost per session", "Main set, list prices; level 0 costs nothing",
            [("", names, costs)], [("$ per session", "s1")], top, lambda v: f"${v:.4f}",
            ref=(ARTICLE_USD_PER_SESSION, f"Article: ${ARTICLE_USD_PER_SESSION:.4f}")))
    return written
