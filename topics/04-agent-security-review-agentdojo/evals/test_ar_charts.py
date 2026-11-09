from test_ar_run import _write_run

from agentreview.charts import build_charts
from agentreview.data import load_key

ACT = {"score": 80, "band": "act", "findings": [], "status": "ok", "hits": [], "tries": ["ok"]}
ROUTINE = {"score": 0, "band": "routine", "findings": [], "status": "ok", "hits": [], "tries": ["ok"]}


def test_no_runs_means_no_charts(tmp_path):
    assert build_charts(tmp_path / "runs", tmp_path / "out") == []


def test_charts_are_svg_with_labels_values_and_the_article_reference(tmp_path):
    runs = tmp_path / "runs"
    for set_name in ("main", "test"):
        kind = load_key(set_name)
        for lv in ("0", "1", "2"):
            _write_run(runs, set_name, lv, [lambda sid, k=kind: ACT if k[sid] == "bad" else ROUTINE] * 2)
    for lv in ("1", "2"):
        _write_run(runs, "fooled", lv, [lambda sid: ROUTINE] * 2)
    paths = build_charts(runs, tmp_path / "out")
    names = sorted(p.name for p in paths)
    assert names == ["caught-by-style.svg", "caught-vs-false-alarms.svg", "cost-per-session.svg", "fooled.svg"]
    main = (tmp_path / "out" / "caught-vs-false-alarms.svg").read_text(encoding="utf-8")
    assert main.startswith("<svg") and "Caught" in main and "False alarms" in main and "Held-out set" in main
    assert ">100%<" in main and ">0%<" in main  # every bar carries its value (relief rule for low-contrast slots)
    assert "prefers-color-scheme: dark" in main
    cost = (tmp_path / "out" / "cost-per-session.svg").read_text(encoding="utf-8")
    assert "Article" in cost and "$0.0045" in cost
