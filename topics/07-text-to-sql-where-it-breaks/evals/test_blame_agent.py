import pytest

from blame_helpers import make_dbs
from sqlblame.agent import pick_tables, read_tables
from sqlblame.levels import Ctx
from sqlblame.warehouse import load_warehouse
from sqlloop.models import Question


@pytest.fixture
def cards(tmp_path):
    paths = make_dbs(tmp_path)
    return load_warehouse(["shop", "zoo"], path_of=lambda d: paths[d])


def test_reads_comma_and_newline_lists(cards):
    assert read_tables("<tables>shop.Customer,\nshop.orders</tables>", cards) == ([("shop", "Customer"), ("shop", "orders")], [])


def test_odd_spelling(cards):
    text = '<tables>`SHOP.customer`, "zoo.animal", keeper</tables>'
    assert read_tables(text, cards) == ([("shop", "Customer"), ("zoo", "animal"), ("zoo", "keeper")], [])


def test_duplicates_dropped(cards):
    assert read_tables("<tables>shop.orders, shop.orders</tables>", cards) == ([("shop", "orders")], [])


def test_unknown_is_made_up(cards):
    assert read_tables("<tables>shop.payments</tables>", cards) == ([], ["shop.payments"])


def test_no_tag_falls_back_to_whole_text_lines(cards):
    assert read_tables("I would use:\nshop.orders\nthat's all", cards) == ([("shop", "orders")], [])


def test_pick_tables_sends_cards_as_system(cards):
    seen = []

    def fake(prompt, *, cached_system="", label="", **kw):
        seen.append((prompt, cached_system, label))
        return "<thoughts>x</thoughts><tables>zoo.keeper</tables>"

    q = Question(1, "zoo", "Who keeps the lion?", "", "SELECT 1", "simple")
    out = pick_tables(q, Ctx("m", llm=fake), cards)
    prompt, system, label = seen[0]
    assert "shop.Customer: id INTEGER, name TEXT" in system and "Who keeps the lion?" in prompt and label == "agent"
    assert out["picked"] == [["zoo", "keeper"]] and out["made_up"] == []
