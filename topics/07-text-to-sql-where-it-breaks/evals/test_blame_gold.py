import collections
import time

import pytest

from blame_helpers import make_dbs
from sqlblame.gold_tables import build, tables_read
from sqlloop.data import RAW_DIR


@pytest.fixture
def shop(tmp_path):
    return make_dbs(tmp_path)["shop"]


def test_join_lists_both_tables(shop):
    assert tables_read(shop, "SELECT c.name FROM Customer c JOIN orders o ON o.cid = c.id") == ["Customer", "orders"]


def test_subquery_and_repeat_listed_once(shop):
    sql = "SELECT name FROM Customer WHERE id IN (SELECT cid FROM orders) AND id IN (SELECT cid FROM orders)"
    assert tables_read(shop, sql) == ["Customer", "orders"]


def test_case_and_quotes_use_master_spelling(shop):
    assert tables_read(shop, 'SELECT * FROM "customer"') == ["Customer"]


def test_does_not_execute(shop):
    slow = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT count(*) FROM n, Customer"
    start = time.monotonic()
    assert tables_read(shop, slow) == ["Customer"]
    assert time.monotonic() - start < 1


@pytest.mark.skipif(not (RAW_DIR / "dev_databases").exists(), reason="BIRD databases not downloaded")
def test_real_gold_tables():
    gold = build()
    assert len(gold) == 120 and all(gold.values())
    from sqlloop.data import load_set
    for name, want in (("main", {1: 13, 2: 34, 3: 12, 4: 1}), ("test", {1: 12, 2: 33, 3: 10, 4: 5})):
        got = collections.Counter(len(gold[str(q.qid)]) for q in load_set(name))
        assert dict(got) == want
