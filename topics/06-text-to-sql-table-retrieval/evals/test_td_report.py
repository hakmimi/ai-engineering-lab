import pytest

from shared.runs import save_run
from tablefind import data, report
from tablefind.build_data import build
from td_helpers import make_raw


@pytest.fixture
def key_set(tmp_path, monkeypatch):
    out = tmp_path / "data"
    build(make_raw(tmp_path), out)
    monkeypatch.setattr(data, "DATA", out)
    s = "main" if data.load_questions("main") else "test"
    return s, data.load_key(s)


def _run(key, level, limit=None, partial=False, top20=False):
    answers = {q: {"picks": sorted(g), "top20": sorted(g) if top20 else None, "made_up": [], "filled": 0, "status": "ok"}
               for q, g in key.items()}
    rep = {"answers": answers, "seconds": {q: 1.0 for q in key}, "cost_usd": {q: 0.001 for q in key},
           "calls": {q: 1 for q in key}, "errors": {}}
    return {"model": "gpt-6-luna", "embed_model": "x", "limit": limit, "partial": partial, "n": len(key),
            "cost_usd": 0.001 * len(key), "repeats": [rep]}


def test_report_says_not_run(tmp_path, key_set):
    text = report.build_results(tmp_path / "runs")
    for name in report.LEVEL_NAMES.values():
        assert f"| {name} | not run |" in text


def test_report_ignores_smoke_runs(tmp_path, key_set):
    s, key = key_set
    runs = tmp_path / "runs"
    save_run(runs, s, "1", _run(key, "1", limit=5))
    text = report.build_results(runs)
    assert f"| {report.LEVEL_NAMES['1']} | not run |" in text


def test_report_shows_scores_from_full_runs(tmp_path, key_set):
    s, key = key_set
    runs = tmp_path / "runs"
    save_run(runs, s, "2", _run(key, "2", top20=True))
    text = report.build_results(runs)
    assert f"| {report.LEVEL_NAMES['2']} | {len(key)} | 100% | 100% | 100% | 0% | 0.0 (0%) |" in text


def test_charts_written_only_with_data(tmp_path, key_set):
    s, key = key_set
    runs, out = tmp_path / "runs", tmp_path / "charts"
    assert report.build_charts(runs, out) == []
    save_run(runs, s, "0", _run(key, "0"))
    names = sorted(p.name for p in report.build_charts(runs, out))
    assert "all-found.svg" in names and "ceiling.svg" not in names


def test_cost_per_question_uses_first_repeat_only(tmp_path, key_set):
    s, key = key_set
    r = _run(key, "2", top20=True)
    cheap = {**r["repeats"][0], "cost_usd": {q: 0.0001 for q in key}}
    r["repeats"].append(cheap)  # repeat 2 hit the provider's prompt cache
    assert report.summary(r, key)["usd"] == pytest.approx(0.001)


def test_report_shows_filled_tables(tmp_path, key_set):
    s, key = key_set
    r = _run(key, "2", top20=True)
    first = next(iter(r["repeats"][0]["answers"].values()))
    first["filled"] = 3
    out = report.summary(r, key)
    assert out["filled_avg"] == pytest.approx(3 / len(key))
    assert out["filled_share"] == pytest.approx(1 / len(key))
    save_run(tmp_path / "runs", s, "2", r)
    assert "Filled from search" in report.build_results(tmp_path / "runs")


def test_level4_and_control_come_from_level3_with_no_extra_cost(tmp_path, key_set):
    s = next(x for x in ("main", "test") if any(len(g) == 2 for g in data.load_key(x).values()))
    key = data.load_key(s)
    r = _run(key, "3", top20=True)
    for q, a in r["repeats"][0]["answers"].items():
        if key[q] == {"alpha_large.projects", "alpha_large.sites"}:
            a["picks"], a["top20"] = ["alpha_large.projects"], ["alpha_large.projects", "beta_large.plants"]
    save_run(tmp_path / "runs", s, "3", r)
    runs = report.level_runs(tmp_path / "runs", s)
    assert runs["4"]["derived_from"] == "3" and runs["4c"]["derived_from"] == "3"
    four = runs["4"]["repeats"][0]["answers"]
    control = runs["4c"]["repeats"][0]["answers"]
    q = next(q for q in key if len(key[q]) == 2)
    assert four[q]["picks"] == ["alpha_large.projects", "alpha_large.sites"]
    assert control[q]["picks"] == ["alpha_large.projects", "beta_large.plants"]
    assert report.summary(runs["4"], key)["all_found"] == 1.0
    assert report.summary(runs["4c"], key)["all_found"] < 1.0
    assert report.summary(runs["4"], key)["usd"] == report.summary(runs["3"], key)["usd"]
    assert "hand over 10 tables" in report.build_results(tmp_path / "runs")
