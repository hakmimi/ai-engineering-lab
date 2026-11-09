import json

from shared.runs import latest_run, over_ceiling, save_run, spent_so_far


def test_spent_so_far_sums_every_run_file_and_skips_bad_ones(tmp_path):
    (tmp_path / "main").mkdir()
    (tmp_path / "main" / "a.json").write_text(json.dumps({"cost_usd": 0.25}), encoding="utf-8")
    (tmp_path / "main" / "b.json").write_text(json.dumps({"cost_usd": 0.5}), encoding="utf-8")
    (tmp_path / "main" / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "main" / "list.json").write_text("[1, 2]", encoding="utf-8")
    assert spent_so_far(tmp_path) == 0.75


def test_spent_so_far_on_missing_folder_is_zero(tmp_path):
    assert spent_so_far(tmp_path / "nope") == 0.0


def test_over_ceiling():
    assert over_ceiling(spent=4.0, estimate=1.5, ceiling=5.0)
    assert not over_ceiling(spent=4.0, estimate=1.0, ceiling=5.0)


def test_save_run_writes_stamped_file_under_the_set(tmp_path):
    path = save_run(tmp_path, "main", "2", {"cost_usd": 0.1}, stamp="20261109-120000")
    assert path == tmp_path / "main" / "level-2-20261109-120000.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["cost_usd"] == 0.1 and saved["level"] == "2" and saved["set"] == "main"
    assert saved["created"] == "20261109-120000"


def test_latest_run_skips_smoke_and_partial_runs(tmp_path):
    save_run(tmp_path, "main", "1", {"limit": None, "partial": False, "n": "old"}, stamp="20261101-000000")
    save_run(tmp_path, "main", "1", {"limit": None, "partial": False, "n": "full"}, stamp="20261102-000000")
    save_run(tmp_path, "main", "1", {"limit": 3, "partial": False, "n": "smoke"}, stamp="20261103-000000")
    save_run(tmp_path, "main", "1", {"limit": None, "partial": True, "n": "cut"}, stamp="20261104-000000")
    assert latest_run(tmp_path, "main", "1")["n"] == "full"


def test_latest_run_none_when_nothing_ran(tmp_path):
    assert latest_run(tmp_path, "test", "2") is None
