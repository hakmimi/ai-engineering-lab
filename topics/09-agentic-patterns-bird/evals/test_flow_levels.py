import pytest

from agentflow.levels import AGENT_MAX_STEPS, LEVELS, Ctx, solve, vote
from flow_helpers import FakeLLM, make_dbs
from sqlblame.warehouse import load_warehouse
from sqlloop.execute import ExecResult
from sqlloop.models import Question

Q = Question(7, "shop", "How much did Ann spend?", "Ann is customer 1", "SELECT 'GOLD-MARK' FROM orders", "simple")
ROUTE_SHOP = "<thoughts>orders</thoughts><database>shop</database>"
SQL_SUM = "<sql>SELECT sum(total) FROM orders WHERE cid = 1</sql>"


@pytest.fixture
def world(tmp_path):
    paths = make_dbs(tmp_path)
    path_of = lambda d: paths[d]
    return load_warehouse(["shop", "zoo"], path_of=path_of), path_of


def run(level, replies, world):
    cards, path_of = world
    llm = FakeLLM(replies)
    out = solve(Q, level, Ctx("m", llm=llm), cards, path_of=path_of)
    return out, llm


def test_levels_listed():
    assert LEVELS == ("0", "1", "1h", "2", "3", "4", "5")


def test_level_0_sees_every_database_and_names_one(world):
    out, llm = run("0", {"write": "<database>shop</database>" + SQL_SUM}, world)
    assert (out["db"], out["sql"], out["stop"]) == ("shop", "SELECT sum(total) FROM orders WHERE cid = 1", "ok")
    (label, prompt, system), = llm.calls
    assert "-- database: shop" in system and "-- database: zoo" in system and "CREATE TABLE animal" in system
    assert "<database></database>" in prompt


def test_level_0_unknown_database_is_no_answer(world):
    out, _ = run("0", {"write": "<database>bank</database>" + SQL_SUM}, world)
    assert (out["db"], out["sql"], out["stop"]) == (None, "", "db_unreadable")


def test_level_1_router_then_writer_on_one_database(world):
    out, llm = run("1", {"route": ROUTE_SHOP, "write": SQL_SUM}, world)
    assert llm.labels() == ["route", "write"]
    assert "zoo.animal" in llm.calls[0][2]  # the router sees every table card
    assert "CREATE TABLE Customer" in llm.calls[1][2] and "animal" not in llm.calls[1][2]
    assert (out["db"], out["stop"], out["handoff"]) == ("shop", "ok", False)


def test_level_1_unreadable_route_is_no_answer(world):
    out, llm = run("1", {"route": "<database>HUMAN</database>"}, world)
    assert llm.labels() == ["route"]
    assert (out["db"], out["sql"], out["stop"]) == (None, "", "route_unreadable")


def test_level_1h_handoff_goes_to_the_stand_in_human(world):
    out, llm = run("1h", {"route": "<database>HUMAN</database>", "write": SQL_SUM}, world)
    assert "HUMAN" in llm.calls[0][1]
    assert (out["db"], out["handoff"], out["stop"]) == ("shop", True, "ok")


def test_level_1h_without_handoff(world):
    out, _ = run("1h", {"route": ROUTE_SHOP, "write": SQL_SUM}, world)
    assert out["handoff"] is False


@pytest.mark.parametrize("level", ["0", "1", "1h", "2", "3", "4", "5"])
def test_gold_sql_never_reaches_a_prompt(level, world):
    replies = {"write": "<database>shop</database>" + SQL_SUM, "route": ROUTE_SHOP, "plan": "<subquestion>a</subquestion><subquestion>b</subquestion>",
               "worker": SQL_SUM, "combine": SQL_SUM, "generate": SQL_SUM, "grade": "<evaluation>PASS</evaluation>",
               "agent": "<tool>answer</tool><database>shop</database>" + SQL_SUM}
    _, llm = run(level, replies, world)
    assert llm.calls
    assert all("GOLD-MARK" not in p and "GOLD-MARK" not in s for _, p, s in llm.calls)


R = lambda rows: ExecResult(rows, "", len(rows))
FAIL = ExecResult(None, "no such table: x")


def test_vote_majority():
    assert vote([R([(1,)]), R([(2,)]), R([(2,)])]) == 1


def test_vote_tie_goes_to_the_earliest():
    assert vote([R([(1,)]), R([(2,)]), R([(3,)])]) == 0


def test_vote_failures_lose_unless_all_fail():
    assert vote([FAIL, R([(2,)]), FAIL]) == 1
    assert vote([FAIL, R([(1,)]), R([(2,)])]) == 1
    assert vote([FAIL, FAIL, FAIL]) == 0


def test_vote_ignores_row_order():
    assert vote([R([(1,), (2,)]), R([(3,)]), R([(2,), (1,)])]) == 0


def test_level_2_three_writers_and_a_vote(world):
    writes = ["<sql>SELECT count(*) FROM orders</sql>", SQL_SUM, "<sql>SELECT 12.5</sql>"]
    out, llm = run("2", {"route": ROUTE_SHOP, "write": writes}, world)
    assert sorted(llm.labels()) == ["route", "write-1", "write-2", "write-3"]
    assert out["agree"] == 2 and out["sql"] in ("SELECT sum(total) FROM orders WHERE cid = 1", "SELECT 12.5")


def test_level_3_one_subquestion_is_one_worker_on_the_question(world):
    out, llm = run("3", {"route": ROUTE_SHOP, "plan": "<subquestion>How much did Ann spend?</subquestion>",
                         "worker": SQL_SUM}, world)
    assert llm.labels() == ["route", "plan", "worker-1"]
    assert "Question: How much did Ann spend?" in llm.calls[2][1]
    assert (out["n_sub"], out["sql"]) == (1, "SELECT sum(total) FROM orders WHERE cid = 1")


def test_level_3_unreadable_plan_counts_as_one(world):
    out, llm = run("3", {"route": ROUTE_SHOP, "plan": "no tags", "worker": SQL_SUM}, world)
    assert out["n_sub"] == 1 and llm.labels()[-1] == "worker-1"


def test_level_3_two_subquestions_then_combine(world):
    out, llm = run("3", {"route": ROUTE_SHOP, "plan": "<subquestion>Ann's id</subquestion><subquestion>orders of id 1</subquestion>",
                         "worker": ["<sql>SELECT id FROM Customer WHERE name = 'Ann'</sql>", "<sql>SELECT total FROM orders</sql>"],
                         "combine": "<sql>SELECT 1</sql>"}, world)
    assert sorted(llm.labels()) == ["combine", "plan", "route", "worker-1", "worker-2"]
    combine_prompt = [p for lb, p, _ in llm.calls if lb == "combine"][0]
    assert "Ann's id" in combine_prompt and "orders of id 1" in combine_prompt and "9.5" in combine_prompt
    assert (out["n_sub"], out["sql"]) == (2, "SELECT 1")


def test_level_4_is_topic_05s_loop_after_the_router(world):
    out, llm = run("4", {"route": ROUTE_SHOP, "generate": ["<sql>SELECT 1</sql>", SQL_SUM],
                         "grade": ["<evaluation>FAIL</evaluation><feedback>wrong</feedback>", "<evaluation>PASS</evaluation>"]}, world)
    assert llm.labels() == ["route", "generate-1", "grade-1", "generate-2", "grade-2"]
    assert "When run on the database" in llm.calls[2][1]  # the grader sees the rows (topic 05 level 3)
    assert (out["rounds"], out["sql"], out["stop"]) == (2, "SELECT sum(total) FROM orders WHERE cid = 1", "pass")


def test_level_5_agent_uses_tools_then_answers(world):
    steps = ["<tool>describe</tool><database>shop</database>",
             "<tool>run_sql</tool><database>shop</database><sql>SELECT total FROM orders</sql>",
             "<tool>answer</tool><database>shop</database>" + SQL_SUM]
    out, llm = run("5", {"agent": steps}, world)
    assert llm.labels() == ["agent-1", "agent-2", "agent-3"]
    assert "shop: Customer, orders" in llm.calls[0][2]
    assert "CREATE TABLE orders" in llm.calls[1][1]  # describe's observation is in the next step
    assert "9.5" in llm.calls[2][1]  # run_sql's rows too
    assert (out["db"], out["sql"], out["stop"], out["steps"]) == ("shop", "SELECT sum(total) FROM orders WHERE cid = 1", "answer", 3)


def test_level_5_unknown_database_and_bad_actions_are_observations(world):
    steps = ["<tool>describe</tool><database>bank</database>", "let me think", "<tool>answer</tool><database>bank</database><sql>SELECT 1</sql>",
             "<tool>answer</tool><database>zoo</database><sql>SELECT 1</sql>"]
    out, llm = run("5", {"agent": steps}, world)
    assert "Unknown database" in llm.calls[1][1] and "Could not read a tool call" in llm.calls[2][1]
    assert (out["db"], out["steps"]) == ("zoo", 4)


def test_level_5_stops_at_the_cap_without_an_answer(world):
    out, llm = run("5", {"agent": lambda p: "<tool>describe</tool><database>zoo</database>"}, world)
    assert len(llm.calls) == AGENT_MAX_STEPS == 10
    assert "last step" in llm.calls[-1][1]
    assert (out["db"], out["sql"], out["stop"], out["steps"]) == (None, "", "cap", 10)


def test_unknown_level(world):
    with pytest.raises(ValueError):
        run("9", {}, world)
