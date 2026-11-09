# Articles to validate

The backlog for the `validate-article` skill (`.claude/skills/validate-article/`). "Do the next one" takes the top `waiting` row.
Status: `waiting` → `in progress` → `published`.

| # | Article | Status | Topic folder | Post |
|---|---|---|---|---|
| 01–02 | [Basic workflows](https://platform.claude.com/cookbook/patterns-agents-basic-workflows) | published | `topics/01-prompt-vs-workflow-claimsflow`, `topics/02-prompt-vs-workflow-contract-nli` | https://hakmimi.github.io/Blog/posts/01-prompt-vs-workflow/ |
| 03 | [Latency optimization: input tokens](https://platform.claude.com/cookbook/latency-optimization-latency-optimization#input-token-management) | published | `topics/03-input-tokens-latency-contract-nli` | https://hakmimi.github.io/Blog/posts/03-input-tokens-latency/ |
| 04 | [Agent security review with Managed Agents](https://platform.claude.com/cookbook/managed-agents-cma-agent-security-review) | published 2026-11-09 | `topics/04-agent-security-review-agentdojo` | https://hakmimi.github.io/Blog/posts/04-agent-security-review/ |
| 05 | [Evaluator-optimizer](https://platform.claude.com/cookbook/patterns-agents-evaluator-optimizer) | in progress | `topics/05-evaluator-optimizer-text-to-sql` | |
| 06 | [LinkedIn: Practical text-to-SQL for data analytics](https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics) | in progress | `topics/06-text-to-sql-table-retrieval` | |

## Ideas for later

- **Business-definition lookup for table finding** (from topic 06): search LiveSQLBench's per-database knowledge base with the question and add matched definitions before table search. LinkedIn's "domain knowledge" lever.
