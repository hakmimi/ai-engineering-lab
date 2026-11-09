# Data notice

The questions, hints (`evidence`), gold SQL and difficulty tags in `main.json` and `test.json` come from
**BIRD Mini-Dev** (the BIRD-SQL team; [github.com/bird-bench/mini_dev](https://github.com/bird-bench/mini_dev)),
released under **CC BY-SA 4.0**. These two files are a derived subset and are shared under the same licence.

**What I took:** from `minidev.zip` (official link `bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip`), only
`MINIDEV/mini_dev_sqlite.json` (500 questions), `MINIDEV/dev_tables.json` and the 11 SQLite databases in
`MINIDEV/dev_databases/`, fetched with HTTP range requests. The MySQL and PostgreSQL dumps were not downloaded.
The databases live in `data/raw/` and are **not in git**.

**What I changed:**

- Renamed fields: `question_id` → `qid`, `SQL` → `gold_sql`. Text is unchanged.
- Drew two subsets with a fixed seed (2026), see `sqlloop/build_data.py`: the 11 databases are split 6 / 5;
  `main.json` has 60 questions from the first group, `test.json` 60 from the second, 18 simple, 30 moderate and
  12 challenging each.
- A gold query that failed or ran past 30 s was skipped and the next one taken; those are listed in `build_log.json`.

To rebuild: put the files above in `data/raw/` and run `python -m sqlloop.build_data`.
