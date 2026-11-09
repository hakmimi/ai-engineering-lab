import pytest

from blame_helpers import make_dbs
from sqlblame.warehouse import ALL_DBS, load_warehouse, render_cards, render_tables
from sqlloop.data import RAW_DIR
from sqlloop.schema import render_schema


@pytest.fixture
def dbs(tmp_path):
    paths = make_dbs(tmp_path)
    return paths, (lambda db_id: paths[db_id])


def test_render_tables_all_equals_render_schema(dbs):
    paths, path_of = dbs
    assert render_tables([("shop", "Customer"), ("shop", "orders")], path_of=path_of) == render_schema(paths["shop"])


def test_render_tables_subset_keeps_order(dbs):
    _, path_of = dbs
    text = render_tables([("zoo", "keeper"), ("shop", "orders")], path_of=path_of)
    assert "CREATE TABLE orders" in text and "Customer" not in text
    assert text.index("CREATE TABLE keeper") < text.index("CREATE TABLE orders")
    assert render_tables([], path_of=path_of) == ""


def test_cards_have_db_prefix_and_types(dbs):
    _, path_of = dbs
    cards = load_warehouse(["zoo", "shop"], path_of=path_of)
    text = render_cards(cards)
    assert "shop.Customer: id INTEGER, name TEXT" in text.splitlines()
    assert len(text.splitlines()) == 4
    assert [c.name for c in cards][:2] == ["shop.Customer", "shop.orders"]


@pytest.mark.skipif(not (RAW_DIR / "dev_databases").exists(), reason="BIRD databases not downloaded")
def test_real_warehouse_size():
    cards = load_warehouse(list(ALL_DBS))
    assert len(ALL_DBS) == 11 and len(cards) == 75
    assert sum(len(c.columns) for c in cards) == 798
    assert len({c.table.lower() for c in cards}) == 75
