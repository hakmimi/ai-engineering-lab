"""Pins every prompt topic 09 sends, per level, to the snapshot taken before the levels moved onto shared.patterns.

The full runs were made with the code as it was then; this test proves the move changed no prompt and no outcome.
Regenerate only on purpose:  python topics/09-agentic-patterns-bird/evals/test_flow_same_prompts.py  (writes the file)
"""

import json
import sys
from pathlib import Path

import pytest

from agentflow.levels import Ctx, solve
from flow_helpers import FakeLLM, make_dbs
from sqlblame.warehouse import load_warehouse
from sqlloop.models import Question

SNAPSHOT = Path(__file__).with_name("prompts_snapshot.json")
Q = Question(7, "shop", "How much did Ann spend?", "Ann is customer 1", "SELECT 1", "simple")
SUM = "<sql>SELECT sum(total) FROM orders WHERE cid = 1</sql>"
SHOP = "<database>shop</database>"

SCENARIOS = {
    "0": {"write": SHOP + SUM},
    "1": {"route": SHOP, "write": SUM},
    "1h": {"route": "<database>HUMAN</database>", "write": SUM},
    "2": {"route": SHOP, "write-1": "<sql>SELECT 1</sql>", "write-2": SUM, "write-3": SUM},
    "3-one": {"route": SHOP, "plan": "<subquestion>How much did Ann spend?</subquestion>", "worker-1": SUM},
    "3-two": {"route": SHOP, "plan": "<subquestion>Ann's id</subquestion><subquestion>her orders</subquestion>",
              "worker-1": "<sql>SELECT id FROM Customer WHERE name = 'Ann'</sql>",
              "worker-2": "<sql>SELECT total FROM orders WHERE cid = 1</sql>", "combine": SUM},
    "4": {"route": SHOP, "generate-1": "<sql>SELECT 1</sql>", "grade-1": "<evaluation>FAIL</evaluation><feedback>no</feedback>",
          "generate-2": SUM, "grade-2": "<evaluation>PASS</evaluation>"},
    "5": {"agent-1": "<tool>describe</tool><database>shop</database>",
          "agent-2": "<tool>run_sql</tool><database>shop</database><sql>SELECT total FROM orders</sql>",
          "agent-3": "<tool>answer</tool><database>shop</database>",
          "agent-4": "hmm", "agent-5": "<tool>describe</tool><database>bank</database>",
          "agent-6": "<tool>answer</tool><database>shop</database>" + SUM},
    "5-cap": {"agent": "<tool>describe</tool><database>zoo</database>"},
}
KEYS = ("db", "sql", "stop", "handoff", "agree", "n_sub", "rounds", "steps", "trace")


def capture(tmp: Path) -> dict:
    paths = make_dbs(tmp)
    path_of = lambda d: paths[d]
    cards = load_warehouse(["shop", "zoo"], path_of=path_of)
    snap = {}
    for name, replies in SCENARIOS.items():
        llm = FakeLLM(replies)
        out = solve(Q, name.split("-")[0], Ctx("m", llm=llm), cards, path_of=path_of)
        snap[name] = {"calls": sorted([list(c) for c in llm.calls]), "out": {k: out.get(k) for k in KEYS}}
    return snap


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_prompts_and_outcomes_match_the_snapshot(name, tmp_path):
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))[name]
    got = json.loads(json.dumps(capture(tmp_path)[name]))
    assert got["calls"] == expected["calls"]
    assert got["out"] == expected["out"]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        SNAPSHOT.write_text(json.dumps(capture(Path(d)), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {SNAPSHOT}")
    sys.exit(0)
