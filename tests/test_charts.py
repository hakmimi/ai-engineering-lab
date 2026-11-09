import xml.etree.ElementTree as ET

from shared.charts import DARK, LIGHT, bar_chart, money, pct

NS = "{http://www.w3.org/2000/svg}"


def _svg(**kw):
    args = dict(
        title="Caught vs. false alarms",
        subtitle="Share of sessions",
        panels=[("Main set", ["Level 0", "Level 1"], [[0.5, 0.1], [1.0, 0.0]])],
        series=[("Caught", "s1"), ("False alarms", "s2")],
        xmax=1.0,
        fmt=pct,
    )
    args.update(kw)
    return bar_chart(**args)


def test_output_is_valid_svg_with_title_as_label():
    root = ET.fromstring(_svg())
    assert root.tag == f"{NS}svg"
    assert root.get("aria-label") == "Caught vs. false alarms"


def test_every_value_is_drawn_and_labelled():
    svg = _svg()
    root = ET.fromstring(svg)
    marks = [e for e in root.iter() if e.tag in (f"{NS}path", f"{NS}rect") and e.get("class") in ("s1", "s2")]
    # 4 values -> 4 bars, plus 2 legend swatches
    assert len(marks) == 6
    for label in ("50%", "10%", "100%", "0%"):
        assert f">{label}</text>" in svg


def test_legend_only_for_two_or_more_series():
    one = _svg(panels=[("", ["A"], [[0.3]])], series=[("Only", "s1")])
    assert ">Only</text>" not in one
    assert ">Caught</text>" in _svg()


def test_missing_value_says_not_run():
    svg = _svg(panels=[("", ["A"], [[None, 0.2]])])
    assert "not run" in svg


def test_reference_line_is_dashed_and_labelled():
    svg = _svg(ref=(0.5, "Article: 50%"))
    assert 'stroke-dasharray="4 3"' in svg
    assert ">Article: 50%</text>" in svg


def test_text_is_escaped():
    root = ET.fromstring(_svg(title="A < B & C"))
    assert root.get("aria-label") == "A < B & C"


def test_dark_mode_colours_present():
    svg = _svg()
    assert "prefers-color-scheme: dark" in svg
    assert LIGHT["s1"] in svg and DARK["s1"] in svg


def test_values_above_xmax_are_capped_not_overflowing():
    root = ET.fromstring(_svg(panels=[("", ["A"], [[5.0, 0.0]])]))
    width = float(root.get("width"))
    for e in root.iter(f"{NS}text"):
        assert float(e.get("x", 0)) < width


def test_formatters():
    assert pct(0.634) == "63%"
    assert money(0.0045) == "$0.0045"
