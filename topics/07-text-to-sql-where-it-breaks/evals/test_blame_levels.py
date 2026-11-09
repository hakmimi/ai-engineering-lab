import pytest

import sqlloop.levels as t05
from blame_helpers import make_dbs
from sqlblame.levels import Ctx, solve
from sqlblame.warehouse import load_warehouse
from sqlloop.models import Question
from sqlloop.prompts import SCHEMA_INTRO

Q = Question(7, "shop", "How much did Ann spend?", "Ann is a customer name", "SELECT sum(total) FROM orders", "simple")
SQL = "<sql>SELECT sum(total) FROM orders JOIN Customer ON id = cid WHERE name = 'Ann'</sql>"


class Fake:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, prompt, *, cached_system="", label="", **kw):
        self.calls.append({"prompt": prompt, "system": cached_system, "label": label})
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


@pytest.fixture
def env(tmp_path):
    paths = make_dbs(tmp_path)
    path_of = lambda d: paths[d]
    return paths, path_of, load_warehouse(["shop", "zoo"], path_of=path_of)


def test_level_a_matches_topic05_level0(env):
    paths, path_of, cards = env
    ours, theirs = Fake(SQL), Fake(SQL)
    out = solve(Q, "A", Ctx("m", llm=ours), ["orders"], cards, path_of=path_of)
    t05.solve(Q, "0", t05.Ctx("m", llm=theirs), paths["shop"])
    assert (ours.calls[0]["prompt"], ours.calls[0]["system"]) == (theirs.calls[0]["prompt"], theirs.calls[0]["system"])
    assert out["sql"].startswith("SELECT sum(total)") and out["given_tables"] == [["shop", "Customer"], ["shop", "orders"]]


def test_level_b_shows_only_gold_tables(env):
    _, path_of, cards = env
    fake = Fake(SQL)
    out = solve(Q, "B", Ctx("m", llm=fake), ["orders"], cards, path_of=path_of)
    assert "CREATE TABLE orders" in fake.calls[0]["system"] and "Customer" not in fake.calls[0]["system"]
    assert out["picked"] is None and out["given_tables"] == [["shop", "orders"]]


def test_level_c_writer_gets_picked_tables_from_any_db(env):
    _, path_of, cards = env
    fake = Fake("<tables>zoo.animal</tables>", SQL)
    out = solve(Q, "C", Ctx("m", llm=fake), ["orders"], cards, path_of=path_of)
    assert [c["label"] for c in fake.calls] == ["agent", "write"]
    assert "CREATE TABLE animal" in fake.calls[1]["system"]
    assert out["given_tables"] == [["zoo", "animal"]] and out["picked"] == [["zoo", "animal"]] and not out["agent_empty"]


def test_level_c_agent_empty(env):
    _, path_of, cards = env
    fake = Fake("<tables></tables>", SQL)
    out = solve(Q, "C", Ctx("m", llm=fake), ["orders"], cards, path_of=path_of)
    assert fake.calls[1]["system"] == SCHEMA_INTRO and out["agent_empty"] and out["sql"]


def test_level_c_agent_api_error_raises_before_writer(env):
    _, path_of, cards = env
    fake = Fake(RuntimeError("api down"), SQL)
    with pytest.raises(RuntimeError):
        solve(Q, "C", Ctx("m", llm=fake), ["orders"], cards, path_of=path_of)
    assert len(fake.calls) == 1
