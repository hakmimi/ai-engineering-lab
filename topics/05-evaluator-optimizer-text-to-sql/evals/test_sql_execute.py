from sql_helpers import make_db
from sqlloop.execute import normalize_rows, run_sql, same_result
from sqlloop.schema import render_schema


def test_select_returns_rows(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    r = run_sql(db, "SELECT name FROM school WHERE county = 'Alameda' ORDER BY id")
    assert r.error == ""
    assert r.rows == [("Oak High",), ("Pine Middle",)]


def test_database_is_read_only(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    r = run_sql(db, "INSERT INTO school (id, name) VALUES (9, 'x')")
    assert r.rows is None
    assert "readonly" in r.error.replace(" ", "").lower()
    assert run_sql(db, "SELECT COUNT(*) FROM school").rows == [(4,)]


def test_bad_sql_keeps_the_error_text(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    r = run_sql(db, "SELECT nope FROM school")
    assert r.rows is None
    assert "no such column: nope" in r.error


def test_slow_query_times_out(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    slow = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT MAX(x) FROM c"
    r = run_sql(db, slow, timeout_s=0.5)
    assert r.rows is None
    assert r.error.startswith("timeout")


def test_max_rows_cuts_the_result_but_keeps_the_count(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    r = run_sql(db, "SELECT id FROM school ORDER BY id", max_rows=2)
    assert r.rows == [(1,), (2,)]
    assert r.n_rows == 4


def test_same_result_ignores_order_and_duplicates():
    assert same_result([(1, "a"), (2, "b")], [(2, "b"), (1, "a"), (1, "a")])
    assert not same_result([(1, "a")], [(1, "b")])
    assert not same_result([(1,)], [])


def test_rows_from_json_compare_equal_to_tuples():
    assert same_result([[1, "a"]], [(1, "a")])


def test_bytes_are_normalised_to_text():
    assert normalize_rows([(b"\x01\x02", 3)]) == [("x'0102'", 3)]


def test_schema_has_create_statements_and_samples(tmp_path):
    db = make_db(tmp_path / "t.sqlite")
    text = render_schema(db, sample_rows=3, max_cell=8)
    assert "CREATE TABLE school" in text and "CREATE TABLE score" in text
    assert "Oak High" in text
    assert "Elm Elem..." in text and "Elementary" not in text  # long cell cut
    assert "A school" not in text  # only 3 sample rows: row 4 is left out
    assert "<blob>" in text


def test_lenient_match_allows_extra_and_reordered_columns():
    from sqlloop.execute import lenient_same
    gold = [("0210", 630), ("0890", 593)]
    pred = [(1, "Pacific", 630, "0210"), (2, "University", 593, "0890")]
    assert lenient_same(pred, gold)
    assert not lenient_same([(1, "Pacific", 630, "0999"), (2, "University", 593, "0890")], gold)
    assert not lenient_same([(630,), (593,)], gold)  # a missing column is still wrong
    assert lenient_same([], []) and not lenient_same([(1,)], [])
