# Data notice

`gold_tables.json` lists, for each question of topic 05's main and held-out sets, the tables its gold SQL reads.
It is derived from **BIRD Mini-Dev** (https://github.com/bird-bench/mini_dev), licensed **CC BY-SA 4.0**, so this
file is CC BY-SA 4.0 too. The lists were made by preparing each gold query in SQLite with an authorizer callback
(`SQLITE_READ` events); no SQL is stored here. Built by `python -m sqlblame.gold_tables`.
