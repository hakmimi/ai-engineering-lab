# Data notice

**Questions, schemas and column descriptions:** LiveSQLBench-Large-v1, by the BIRD team (HKU) and Google Cloud.
https://huggingface.co/datasets/birdsql/livesqlbench-large-v1 , **CC BY 4.0**, commit `a418e108d5cbb4cf9b783a928eff5e924ad2460d`.

**Which tables each question needs:** SQL-Schema-Retrieval, subset `livesqlbench_large_table` (qrels), by Zeng, Yu, Mehta, Zhao and Samdani (Snowflake, 2026),
"Finding the Right Tables and Columns: A Benchmark and Corpus-Adaptive Embeddings for SQL Schema Retrieval", arXiv:2607.13311.
https://huggingface.co/datasets/Snowflake/SQL-Schema-Retrieval , commit `e60c65cf9aeab052f0747902d31db1807099fa23`. Its card says to follow each source's licence.

## What I changed

- `tables.json`: each table's columns and types, parsed from the `CREATE TABLE` blocks in `*_schema.txt` (sample rows dropped),
  with each column's description from `*_column_meaning_base.json` (for JSONB columns, only the `column_meaning` text).
- `main.json`, `test.json`: the question text only, with new ids (`m-001`, `t-001`). The 18 databases are split 9 / 9 with seed 2026;
  `build_log.json` records the split and maps each new id to its LiveSQLBench `instance_id`.
- `links.json`: foreign-key links between tables, parsed from the same `CREATE TABLE` blocks (level 4).
- `search_next3.json`: for each question, search ranks 21-23 on level 3's description cards (the level 4c control).
- `summaries.json`: one LLM-written summary per table (`gpt-6-luna`, Pinterest's summary prompt), made from the columns and descriptions above (level 5).
- **Not committed:** `key.json` (the gold table lists) and `raw/`. The BIRD team gates the gold SQL to keep it out of training data;
  I never fetch it. The gold table lists are public in Snowflake's release; `python -m tablefind.build_data` downloads them at the pinned commit
  and rebuilds `key.json`.

These derived files are shared under **CC BY 4.0**, like the source.
