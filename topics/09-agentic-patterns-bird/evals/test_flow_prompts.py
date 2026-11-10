from agentflow.prompts import read_action, read_database, read_subquestions

DBS = ("shop", "zoo")


def test_read_database_takes_the_tag_case_insensitively():
    assert read_database("<thoughts>x</thoughts><database> Shop </database>", DBS) == "shop"


def test_read_database_unknown_name_is_none():
    assert read_database("<database>bank</database>", DBS) is None
    assert read_database("no tag at all", DBS) is None


def test_read_database_human_only_when_allowed():
    assert read_database("<database>HUMAN</database>", DBS) is None
    assert read_database("<database>human</database>", DBS, allow_human=True) == "HUMAN"


def test_read_subquestions_all_then_cap():
    assert read_subquestions("nothing") == []
    two = "<subquestion>a</subquestion>\n<subquestion> b </subquestion>"
    assert read_subquestions(two) == ["a", "b"]
    six = "".join(f"<subquestion>q{i}</subquestion>" for i in range(6))
    assert read_subquestions(six) == ["q0", "q1", "q2", "q3"]


def test_read_action_each_tool():
    assert read_action("<tool>describe</tool><database>zoo</database>") == ("describe", {"database": "zoo", "sql": ""})
    assert read_action("<tool> run_sql </tool><database>zoo</database><sql>SELECT 1</sql>") == \
        ("run_sql", {"database": "zoo", "sql": "SELECT 1"})
    tool, args = read_action("<tool>answer</tool><database>shop</database><sql>```sql\nSELECT a &gt; 1\n```</sql>")
    assert tool == "answer" and args["sql"] == "SELECT a > 1"


def test_read_action_without_a_known_tool():
    assert read_action("I think I should look") == (None, {})
    assert read_action("<tool>drop_table</tool>") == (None, {})


def test_read_action_strips_quotes_and_reads_a_fenced_answer():
    tool, args = read_action("<tool>answer</tool><database>`zoo`</database>\n```sql\nSELECT 1\n```")
    assert (tool, args) == ("answer", {"database": "zoo", "sql": "SELECT 1"})
