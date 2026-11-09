import json

from ndaspeed.report import build_results


def _t(first_text=0.5, total=1.0, input_tokens=100, cached=0, output=10, error=None, request_bytes=1000):
    return {"first_event_s": 0.1, "first_output_s": first_text, "first_text_s": first_text, "total_s": total,
            "request_bytes": request_bytes, "input_tokens": input_tokens, "cached_tokens": cached, "output_tokens": output,
            "reasoning_tokens": 0, "response_id": "r", "text": "", "error": error, "status": None}


def _run(test, records, spent=0.1, started="2026-11-10T10:00:00"):
    return {"test": test, "started": started, "seed": 2026, "models": {"small": "gpt-6-luna"}, "plan": {},
            "records": records, "spent_usd": spent, "stopped": None}


def _write(runs_dir, name, run):
    (runs_dir / name).write_text(json.dumps(run), encoding="utf-8")


def _section(text, test):
    start = text.index(f"## Test {test}")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else None]


def test_missing_test_says_not_run_yet(tmp_path):
    text = build_results(tmp_path)
    for n in "01234":
        assert "Not run yet." in _section(text, n)


def test_warmup_and_errors_left_out_of_stats_but_counted(tmp_path):
    _write(tmp_path, "test0-20261110-100000.json", _run("0", [
        {"variant": "warmup", "model": "gpt-6-luna", "timing": _t(9.0)},
        {"variant": "floor", "model": "gpt-6-luna", "rep": 0, "timing": _t(0.5)},
        {"variant": "error", "model": "gpt-6-luna", "rep": 1, "timing": _t(None, None, error="RateLimitError")},
        {"variant": "floor", "model": "gpt-6-luna", "rep": 1, "timing": _t(0.7)},
    ]))
    s = _section(build_results(tmp_path), "0")
    assert "| 0.60 |" in s  # median of 0.5 and 0.7; the 9.0 warm-up is left out
    assert "9.00" not in s
    assert "| 1 |" in s  # one error counted


def test_test1_shows_slope_and_flags_cold_requests_with_cached_tokens(tmp_path):
    recs = [{"variant": "cold", "model": "gpt-6-luna", "size": size, "round": 0,
             "timing": _t(0.5 + tokens / 400_000, input_tokens=tokens, cached=1024 if size == 50 else 0)}
            for size, tokens in ((20, 20_000), (50, 50_000), (100, 100_000))]
    recs.append({"variant": "cold", "size": 180, "skipped": "not enough NDAs for 180 tokens"})
    _write(tmp_path, "test1-20261110-100000.json", _run("1", recs))
    s = _section(build_results(tmp_path), "1")
    assert "+0.25 s per 100K" in s
    assert "Cold check: 1 request(s) with cached tokens > 0" in s
    assert "not enough NDAs for 180 tokens" in s


def test_test2_reports_cached_share_accuracy_and_turn_split(tmp_path):
    recs = []
    for v, first, cached in (("cache_on", 0.4, 900), ("cache_off", 0.8, 0)):
        for turn in range(3):
            recs.append({"variant": v, "model": "gpt-6-luna", "pack": "long", "chat": 0, "turn": turn,
                         "doc_id": "1", "sid": "nda-1", "label": "entailment", "evidence": [1, 2],
                         "key_label": "entailment", "key_evidence": [1], "fallback": False,
                         "timing": _t(1.0 if turn == 0 else first, input_tokens=1000, cached=0 if turn == 0 else cached)})
    _write(tmp_path, "test2-20261110-100000.json", _run("2", recs))
    s = _section(build_results(tmp_path), "2")
    row_on = next(l for l in s.splitlines() if l.startswith("| long | cache_on"))
    assert "| 1.00 | 0.40 |" in row_on  # turn 1, then turns 2-17
    assert "60%" in row_on  # 1800 cached of 3000 input
    assert "100%" in row_on  # label right


def test_test3_shows_prewarm_hit_rate(tmp_path):
    _write(tmp_path, "test3-20261110-100000.json", _run("3", [
        {"variant": "prewarm_call", "model": "gpt-6-luna", "rep": 0, "timing": _t(None)},
        {"variant": "prewarm", "model": "gpt-6-luna", "rep": 0, "timing": _t(0.6, cached=90_000), "label": "entailment",
         "key_label": "entailment", "evidence": [], "key_evidence": []},
        {"variant": "prewarm", "model": "gpt-6-luna", "rep": 1, "timing": _t(0.9, cached=0), "label": "entailment",
         "key_label": "entailment", "evidence": [], "key_evidence": []},
        {"variant": "cold", "model": "gpt-6-luna", "rep": 0, "timing": _t(1.0), "label": "entailment",
         "key_label": "entailment", "evidence": [], "key_evidence": []},
    ]))
    s = _section(build_results(tmp_path), "3")
    assert "Warm-up hit rate: 1/2" in s


def test_footer_shows_running_total(tmp_path):
    _write(tmp_path, "test0-20261110-100000.json", _run("0", [], spent=1.0))
    _write(tmp_path, "test1-20261110-100000.json", _run("1", [], spent=0.5))
    assert "Total spent: $1.50" in build_results(tmp_path)


def test_latest_run_per_test_wins(tmp_path):
    _write(tmp_path, "test0-20261110-100000.json", _run("0", [{"variant": "floor", "model": "m", "rep": 0, "timing": _t(0.5)}]))
    _write(tmp_path, "test0-20261111-100000.json", _run("0", [{"variant": "floor", "model": "m", "rep": 0, "timing": _t(0.8)}]))
    s = _section(build_results(tmp_path), "0")
    assert "| 0.80 |" in s and "test0-20261111-100000.json" in s
