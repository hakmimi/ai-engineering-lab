"""Blog graphs as plain SVG files (no plotting library needed). Used by every topic's report.

Horizontal bars, thin, square at the baseline and 4px rounded at the data end; every bar carries its
value (slot 3 has a contrast warning, so labels are required); a legend for two or more series; light
and dark colours from the dataviz skill's validated reference palette. Use slots in order: s1, s2, s3.
"muted" is for a reference or chance series, never a fourth category.

    from shared.charts import bar_chart, pct
    svg = bar_chart("Caught vs. false alarms", "Share of sessions flagged",
                    [("Main set", ["Level 0", "Level 1"], [[0.5, 0.1], [1.0, 0.0]])],
                    [("Caught", "s1"), ("False alarms", "s2")], xmax=1.0, fmt=pct)
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape

LIGHT = {"s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "muted": "#898781",
         "ink": "#0b0b0b", "ink2": "#52514e", "axis": "#c3c2b7", "grid": "#e1e0d9"}
DARK = {"s1": "#3987e5", "s2": "#d95926", "s3": "#199e70", "muted": "#898781",
        "ink": "#f0efec", "ink2": "#c3c2b7", "axis": "#383835", "grid": "#2c2c2a"}

WIDTH = 720
LABEL_W = 170  # room for category names
PLOT_W = 440   # leaves room right of the longest bar for its value label
BAR_H = 14
BAR_GAP = 2
GROUP_GAP = 14
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

Panel = tuple[str, list[str], list[list[float | None]]]


def pct(v: float) -> str:
    return f"{v:.0%}"


def money(v: float) -> str:
    return f"${v:.4f}"


def _style() -> str:
    def rules(c: dict) -> str:
        return " ".join(
            [f".{k}{{fill:{v}}}" for k, v in c.items() if k in ("s1", "s2", "s3", "muted")]
            + [f".ink{{fill:{c['ink']}}}", f".ink2{{fill:{c['ink2']}}}",
               f".axis{{stroke:{c['axis']}}}", f".grid{{stroke:{c['grid']}}}", f".ref{{stroke:{c['ink2']}}}"]
        )
    return (f"<style>text{{font-family:{FONT};font-variant-numeric:tabular-nums}} {rules(LIGHT)} "
            f"@media (prefers-color-scheme: dark) {{ {rules(DARK)} }}</style>")


def _bar(x0: float, y: float, w: float, cls: str, tip: str) -> str:
    """Square at the baseline (left), rounded at the data end (right). A zero still shows a 1px stub."""
    if w <= 0:
        return f'<rect x="{x0}" y="{y}" width="1" height="{BAR_H}" class="{cls}"><title>{escape(tip)}</title></rect>'
    r = min(4, w / 2, BAR_H / 2)
    d = (f"M{x0},{y} H{x0 + w - r} A{r},{r} 0 0 1 {x0 + w},{y + r} V{y + BAR_H - r} "
         f"A{r},{r} 0 0 1 {x0 + w - r},{y + BAR_H} H{x0} Z")
    return f'<path d="{d}" class="{cls}"><title>{escape(tip)}</title></path>'


def bar_chart(title: str, subtitle: str, panels: list[Panel], series: list[tuple[str, str]], xmax: float,
              fmt: Callable[[float], str], ref: tuple[float, str] | None = None) -> str:
    """panels: (panel title or "", category names, values[category][series]; None = "not run").
    series: (name, colour class). ref: (x value, label) drawn as a dashed line, e.g. the article's number."""
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
                    w = PLOT_W * max(0.0, min(v, xmax)) / xmax
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
