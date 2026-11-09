# 07 · Results

Built by `python -m sqlblame.report` from the run files only. Do not edit by hand.
Levels: A · the writer gets the whole database, B · only the right tables (Uber's decoupled flow), C · a table agent picks from all 75 tables first (Uber's vanilla flow).

## Main set (60 questions, 6 databases)

Repeats per level: A 3, B 3, C 3. Rates are averaged over repeats; API errors are left out of them and counted.

| Level | Right | simple | moderate | challenging | Runs | Has output | $ / question | s / question | API errors |
|---|---|---|---|---|---|---|---|---|---|
| A · whole database | 52% | 72% | 48% | 33% | 97% | 92% | $0.00020 | 4.9 | 0 |
| B · right tables | 58% | 70% | 58% | 42% | 97% | 95% | $0.00020 | 5.2 | 0 |
| C · table agent, whole warehouse | 53% | 72% | 52% | 28% | 98% | 94% | $0.00032 | 8.0 | 0 |

Gaps, in points of Right:

| Gap | Points | What it shows |
|---|---|---|
| B − A | +6 | what dropping the extra tables is worth |
| B − C | +5 | what the table agent's mistakes cost |
| C − A | +1 | what adding a table agent over the whole warehouse is worth |

The table agent (level C), averaged over repeats:

| Overlap | All found | Exact | Extra tables | Wrong database | Made-up names | Agent empty | Right when all found | Right when some missing |
|---|---|---|---|---|---|---|---|---|
| 95% | 87% | 85% | 0.05 | 0% | 0 | 0 | 60% | 12% |

Uber's cheap signals against the real answer (every final SQL, all levels and repeats):

LLM similarity: "good" means a score ≥ threshold 0.9, picked on the main set and used unchanged here. Unreadable scores: 1.

| Signal | Says "good" when the answer is wrong | Says "good" when it is right |
|---|---|---|
| The query runs | 94% | 100% |
| It returns rows | 87% | 100% |
| LLM similarity to the golden SQL | 35% | 89% |

## Held-out set (60 questions, 5 other databases)

Repeats per level: A 3, B 3, C 3. Rates are averaged over repeats; API errors are left out of them and counted.

| Level | Right | simple | moderate | challenging | Runs | Has output | $ / question | s / question | API errors |
|---|---|---|---|---|---|---|---|---|---|
| A · whole database | 56% | 72% | 47% | 56% | 97% | 94% | $0.00018 | 4.7 | 0 |
| B · right tables | 57% | 69% | 49% | 58% | 98% | 95% | $0.00018 | 4.1 | 0 |
| C · table agent, whole warehouse | 58% | 69% | 52% | 56% | 98% | 94% | $0.00028 | 6.5 | 0 |

Gaps, in points of Right:

| Gap | Points | What it shows |
|---|---|---|
| B − A | +1 | what dropping the extra tables is worth |
| B − C | -1 | what the table agent's mistakes cost |
| C − A | +2 | what adding a table agent over the whole warehouse is worth |

The table agent (level C), averaged over repeats:

| Overlap | All found | Exact | Extra tables | Wrong database | Made-up names | Agent empty | Right when all found | Right when some missing |
|---|---|---|---|---|---|---|---|---|
| 96% | 92% | 88% | 0.07 | 0% | 0 | 0 | 63% | 0% |

Uber's cheap signals against the real answer (every final SQL, all levels and repeats):

LLM similarity: "good" means a score ≥ threshold 0.9, picked on the main set and used unchanged here. Unreadable scores: 0.

| Signal | Says "good" when the answer is wrong | Says "good" when it is right |
|---|---|---|
| The query runs | 95% | 100% |
| It returns rows | 88% | 100% |
| LLM similarity to the golden SQL | 26% | 88% |

Total spent on this topic (all run and judge files, smoke included): $0.33
