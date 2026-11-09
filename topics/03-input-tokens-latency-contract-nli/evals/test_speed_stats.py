import json
import random

import pytest

from ndaspeed.cost import Budget, BudgetExceeded, cost_of, spent_in_runs
from ndaspeed.stats import bootstrap_diff, median, p90, slope_per_100k, values
from ndaspeed.timer import Timing


def test_median_and_p90_ignore_none():
    xs = [None, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert values(xs) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert median(xs) == 5.5
    assert p90(xs) == 9


def test_median_of_empty_is_none():
    assert median([]) is None and p90([None]) is None


def test_slope_per_100k_exact_line():
    assert slope_per_100k([0, 100_000, 200_000], [0.5, 0.75, 1.0]) == pytest.approx(0.25)


def test_bootstrap_diff_brackets_true_shift():
    rng = random.Random(1)
    a = [rng.uniform(0.4, 0.6) for _ in range(30)]
    b = [x + 1.0 for x in a]
    low, high = bootstrap_diff(a, b, random.Random(2))
    assert low <= 1.0 <= high


def test_cost_of_prices_cached_tokens_at_cache_rate():
    t = Timing(0.1, 0.1, 0.1, 0.2, 10, input_tokens=1000, cached_tokens=600, output_tokens=100)
    assert cost_of(t, "gpt-6-luna") == pytest.approx((400 * 0.10 + 600 * 0.01 + 100 * 0.50) / 1e6)


def test_budget_stops_before_crossing_limit():
    b = Budget(1.0)
    b.before(0.6)
    b.add(0.6)
    with pytest.raises(BudgetExceeded):
        b.before(0.5)
    assert b.spent_usd == 0.6


def test_spent_in_runs_sums_run_files(tmp_path):
    (tmp_path / "test1-a.json").write_text(json.dumps({"spent_usd": 1.25}))
    (tmp_path / "test2-b.json").write_text(json.dumps({"spent_usd": 0.5}))
    (tmp_path / "notes.json").write_text(json.dumps({"spent_usd": 99}))
    assert spent_in_runs(tmp_path) == pytest.approx(1.75)
    assert spent_in_runs(tmp_path / "missing") == 0.0


def test_spent_in_runs_counts_smoke_runs_in_subfolders(tmp_path):
    (tmp_path / "smoke").mkdir()
    (tmp_path / "smoke" / "test1-x.json").write_text(json.dumps({"spent_usd": 0.3}))
    (tmp_path / "test0-a.json").write_text(json.dumps({"spent_usd": 0.1}))
    assert spent_in_runs(tmp_path) == pytest.approx(0.4)
