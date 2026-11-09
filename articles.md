# Articles to validate

The backlog for the `validate-article` skill (`.claude/skills/validate-article/`). "Do the next one" takes the top `waiting` row.
Status: `waiting` → `in progress` → `published`.

| # | Article | Status | Topic folder | Post |
|---|---|---|---|---|
| 01–02 | [Basic workflows](https://platform.claude.com/cookbook/patterns-agents-basic-workflows) | published | `topics/01-prompt-vs-workflow-claimsflow`, `topics/02-prompt-vs-workflow-contract-nli` | https://hakmimi.github.io/Blog/posts/01-prompt-vs-workflow/ |
| 03 | [Latency optimization: input tokens](https://platform.claude.com/cookbook/latency-optimization-latency-optimization#input-token-management) | published | `topics/03-input-tokens-latency-contract-nli` | https://hakmimi.github.io/Blog/posts/03-input-tokens-latency/ |
| 04 | [Agent security review with Managed Agents](https://platform.claude.com/cookbook/managed-agents-cma-agent-security-review) | published 2026-11-09 | `topics/04-agent-security-review-agentdojo` | https://hakmimi.github.io/Blog/posts/04-agent-security-review/ |
| 05 | [Evaluator-optimizer](https://platform.claude.com/cookbook/patterns-agents-evaluator-optimizer) | published 2026-11-09 | `topics/05-evaluator-optimizer-text-to-sql` | https://hakmimi.github.io/Blog/posts/05-evaluator-optimizer/ |
| 06 | [LinkedIn: Practical text-to-SQL for data analytics](https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics) | published 2026-11-16 (scheduled) | `topics/06-text-to-sql-table-retrieval` | https://hakmimi.github.io/Blog/posts/06-text-to-sql-table-retrieval/ |
| 07 | [Uber: QueryGPT](https://www.uber.com/lb/en/blog/query-gpt/) | published 2026-11-19 (scheduled) | `topics/07-text-to-sql-where-it-breaks` | https://hakmimi.github.io/Blog/posts/07-text-to-sql-where-it-breaks/ |
| next free | Follow-up to 06: **can better search fix it?** (same [LinkedIn](https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics) and [Pinterest](https://medium.com/pinterest-engineering/how-we-built-text-to-sql-at-pinterest-30bad30dabff) articles) | waiting | | |

**The follow-up to 06, in short.** In topic 06, the LLM kept nearly every needed table it was shown. What limited it was search: in about 4 of 10 held-out questions, a needed table never reached the top 20. Same data, sets and answer key as 06 (LiveSQLBench-Large, 971 tables), so the numbers compare directly. Levels to test:
- a **bigger shortlist**: show the LLM the top 30 or 40 instead of 20 (does the ceiling rise, and does the LLM still pick well?)
- **hybrid search**: BM25 + embeddings combined (level 0 was weak alone, but it may catch names that embeddings miss)
- a **5c control** for 06's level 5j (summaries + search ranks 21-23), which 06 didn't have
- maybe the business-definition lookup below as one more level
Rough cost: about $1-3. Take the number when it starts (08 is in use by another branch).

## Ideas for later

- **Business-definition lookup for table finding** (from topic 06): search LiveSQLBench's per-database knowledge base with the question and add matched definitions before table search. LinkedIn's "domain knowledge" lever.
