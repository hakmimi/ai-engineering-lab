import pytest

from sql_helpers import make_db
from sqlloop.levels import Ctx, solve
from sqlloop.models import Question
from sqlloop.prompts import read_grade, read_sql

Q = Question(1, "t", "Which Alameda schools are there?", "Alameda is a county", "SELECT name FROM school WHERE county = 'Alameda'", "simple")
GOOD = "<thoughts>t</thoughts><sql>SELECT name FROM school WHERE county = 'Alameda'</sql>"
BAD_COL = "<sql>SELECT nope FROM school</sql>"
EMPTY = "<sql>SELECT name FROM school WHERE county = 'alameda'</sql>"


class FakeLLM:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, prompt, *, cached_system="", label="", **kw):
        self.calls.append({"prompt": prompt, "system": cached_system, "label": label})
        return self.answers.pop(0)


def grade(v, fb="fine"):
    return f"<evaluation>{v}</evaluation><feedback>{fb}</feedback>"


@pytest.fixture
def db(tmp_path):
    return make_db(tmp_path / "t.sqlite")


def run(level, answers, db):
    llm = FakeLLM(answers)
    out = solve(Q, level, Ctx(model="m", llm=llm), db)
    return out, llm


def test_read_sql_handles_tags_and_fences():
    assert read_sql("<sql>\n```sql\nSELECT 1;\n```\n</sql>") == "SELECT 1;"
    assert read_sql("Here:\n```sql\nSELECT 2\n```") == "SELECT 2"
    assert read_sql("no query") == ""


def test_read_grade_normalises_and_rejects_unknown():
    assert read_grade(grade("pass")) == ("PASS", "fine")
    assert read_grade(grade("Needs improvement", "join"))[0] == "NEEDS_IMPROVEMENT"
    assert read_grade(grade("maybe"))[0] is None
    assert read_grade("nothing")[0] is None


def test_level0_is_one_call_and_never_shows_gold(db):
    out, llm = run("0", [GOOD], db)
    assert len(llm.calls) == 1 and out["stop"] == "one_shot"
    assert out["final_sql"].startswith("SELECT name")
    text = llm.calls[0]["prompt"] + llm.calls[0]["system"]
    assert Q.gold_sql not in text and "simple" not in text
    assert "Alameda is a county" in text and "CREATE TABLE school" in text


def test_level1_stops_on_pass(db):
    out, llm = run("1", [GOOD, grade("PASS")], db)
    assert len(llm.calls) == 2 and out["stop"] == "pass"
    assert out["rounds"][0]["verdict"] == "PASS"


def test_level1_grader_does_not_see_rows(db):
    out, llm = run("1", [GOOD, grade("PASS")], db)
    assert "Oak High" not in llm.calls[1]["prompt"]
    assert "SELECT name FROM school" in llm.calls[1]["prompt"]


def test_level1_regenerates_with_feedback_history(db):
    out, llm = run("1", [BAD_COL, grade("FAIL", "column nope does not exist"), GOOD, grade("PASS")], db)
    assert len(out["rounds"]) == 2 and out["stop"] == "pass"
    second_gen = llm.calls[2]["prompt"]
    assert "column nope does not exist" in second_gen and "SELECT nope FROM school" in second_gen


def test_level1_stops_at_three_generations(db):
    out, llm = run("1", [BAD_COL, grade("FAIL"), BAD_COL, grade("FAIL"), BAD_COL, grade("FAIL")], db)
    assert len(out["rounds"]) == 3 and out["stop"] == "cap" and len(llm.calls) == 6


def test_unreadable_grade_stops_the_loop(db):
    out, llm = run("1", [GOOD, "I think it is ok"], db)
    assert out["stop"] == "grade_unreadable" and len(llm.calls) == 2


def test_level2_has_no_grader_and_retries_on_error(db):
    out, llm = run("2", [BAD_COL, GOOD], db)
    assert len(llm.calls) == 2 and all(c["label"].startswith("generate") for c in llm.calls)
    assert "no such column: nope" in llm.calls[1]["prompt"]
    assert out["stop"] == "ok" and out["rounds"][1]["n_rows"] == 2


def test_level2_retries_on_zero_rows(db):
    out, llm = run("2", [EMPTY, GOOD], db)
    assert "no rows" in llm.calls[1]["prompt"] and out["stop"] == "ok"


def test_level2_accepts_first_runnable_answer(db):
    out, llm = run("2", [GOOD], db)
    assert len(llm.calls) == 1 and out["stop"] == "ok"


def test_level3_grader_sees_the_rows(db):
    out, llm = run("3", [GOOD, grade("PASS")], db)
    assert "Oak High" in llm.calls[1]["prompt"] and "2 rows" in llm.calls[1]["prompt"]


def test_level3_grader_sees_the_error(db):
    out, llm = run("3", [BAD_COL, grade("FAIL", "bad"), GOOD, grade("PASS")], db)
    assert "no such column: nope" in llm.calls[1]["prompt"]
    assert out["rounds"][0]["error"].startswith("no such column")


def test_read_sql_unescapes_html_entities():
    # the model sometimes escapes < > & inside the <sql> tag, as if it were XML
    assert read_sql("<sql>SELECT a FROM t WHERE x &gt; 1 AND y &lt;= 2 AND z = 'a &amp; b'</sql>") == \
        "SELECT a FROM t WHERE x > 1 AND y <= 2 AND z = 'a & b'"


class ModelLLM(FakeLLM):
    def __call__(self, prompt, *, cached_system="", label="", model="", **kw):
        self.calls.append({"prompt": prompt, "system": cached_system, "label": label, "model": model})
        return self.answers.pop(0)


def test_level4_teacher_grades_with_its_own_model_and_reads_only(db):
    llm = ModelLLM([GOOD, grade("NEEDS_IMPROVEMENT", "check the filter"), GOOD, grade("PASS")])
    out = solve(Q, "4", Ctx(model="student", grader_model="teacher", llm=llm), db)
    assert out["stop"] == "pass" and len(out["rounds"]) == 2
    assert [c["model"] for c in llm.calls] == ["student", "teacher", "student", "teacher"]
    assert out["rounds"][0]["n_rows"] is None  # level 4 never runs the SQL for the grader
    assert "check the filter" in llm.calls[2]["prompt"]


def test_level5_teacher_sees_the_rows(db):
    llm = ModelLLM([EMPTY, grade("FAIL", "no rows"), GOOD, grade("PASS")])
    out = solve(Q, "5", Ctx(model="student", grader_model="teacher", llm=llm), db)
    assert out["rounds"][0]["n_rows"] == 0
    assert llm.calls[1]["model"] == "teacher" and "0 rows" in llm.calls[1]["prompt"].lower()


def test_without_grader_model_the_grader_is_the_writer(db):
    llm = ModelLLM([GOOD, grade("PASS")])
    solve(Q, "1", Ctx(model="m", llm=llm), db)
    assert [c["model"] for c in llm.calls] == ["m", "m"]


def test_read_grade_accepts_a_bare_verdict_without_tags():
    assert read_grade("PASS") == ("PASS", "")
    assert read_grade("  pass\n") == ("PASS", "")
    assert read_grade("NEEDS_IMPROVEMENT\nThe filter should use 'Human'.") == ("NEEDS_IMPROVEMENT", "The filter should use 'Human'.")
    assert read_grade("The query looks fine to me")[0] is None  # free text is still unreadable
