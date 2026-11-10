# 09 · Results

Built by `python -m agentflow.report` from the run files only. Do not edit by hand.
Model: gpt-6-luna. Right = the final query runs on the question's own database and returns the gold rows (order and duplicates ignored). Same answer 3/3 = all repeats end the same way (same database and rows, or the same failure). Rates are averaged over repeats; API errors are left out of them and counted.

## Main set (60 questions, 6 databases)

Repeats per level: 0 3, 1 3, 1h 3, 2 3, 3 3, 4 3, 5 3.

| Level | Right | Right, lowest–highest repeat | Same answer 3/3 | Right 3/3 | Questions in 3/3 | Right database | No answer | SQL errors | $ / question | s / question (median) | Calls / question | API errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 · one prompt | 51% | 48–53% | 70% | 45% | 60 | 100% | 0% | 1% | $0.00040 | 4.9 | 1.0 | 0 |
| 1 · routing | 53% | 52–55% | 78% | 48% | 60 | 100% | 0% | 2% | $0.00028 | 6.7 | 2.0 | 0 |
| 1h · routing + handoff | 52% | 50–53% | 82% | 48% | 60 | 100% | 0% | 3% | $0.00026 | 6.5 | 2.0 | 0 |
| 2 · parallel vote | 55% | 53–57% | 75% | 48% | 60 | 100% | 0% | 2% | $0.00064 | 8.2 | 4.0 | 0 |
| 3 · orchestrator-worker | 54% | 53–55% | 78% | 50% | 60 | 100% | 0% | 3% | $0.00042 | 10.3 | 3.0 | 0 |
| 4 · evaluator-optimizer | 52% | 52–53% | 78% | 47% | 60 | 100% | 0% | 0% | $0.00052 | 10.9 | 3.2 | 0 |
| 5 · free agent | 49% | 48–50% | 62% | 42% | 60 | 100% | 0% | 9% | $0.00039 | 5.7 | 1.5 | 0 |

Noise floor: one question is 1.7 points. Repeats of the same level moved by up to 5 points (level 0), so smaller gaps between levels are not clear effects.

| Level | Inside the pattern |
|---|---|
| 1h · routing + handoff | handed to the human 0%; right on the rest 52% |
| 2 · parallel vote | 2.7 of 3 writers agree with the winner |
| 3 · orchestrator-worker | 1.0 sub-questions on average |
| 4 · evaluator-optimizer | 1.08 rounds on average |
| 5 · free agent | 1.5 steps on average; cap hit 0% |

How the free agent worked (all repeats; API errors left out):

| Before answering, it | Answers | Right | SQL errors |
|---|---|---|---|
| answered at once | 119 of 180 (66%) | 59% | 8% |
| described a database first | 47 of 180 (26%) | 30% | 11% |
| ran SQL first | 14 of 180 (8%) | 36% | 21% |

What if the agent's `database.table` names had worked (offline rerun of its stored queries): 15 answers failed on the prefix, 3 of them would be right; right would be 51% instead of 49%, same answer 3/3 77% instead of 62%.

Workflow minus the free agent (level 5), in points:

| Level | Right | Same answer 3/3 |
|---|---|---|
| 0 · one prompt | +2 | +8 |
| 1 · routing | +3 | +17 |
| 1h · routing + handoff (a person helps) | +2 | +20 |
| 2 · parallel vote | +6 | +13 |
| 3 · orchestrator-worker | +5 | +17 |
| 4 · evaluator-optimizer | +3 | +17 |

## Held-out set (60 questions, 5 other databases)

Repeats per level: 0 3, 1 3, 1h 3, 2 3, 3 3, 4 3, 5 3.

| Level | Right | Right, lowest–highest repeat | Same answer 3/3 | Right 3/3 | Questions in 3/3 | Right database | No answer | SQL errors | $ / question | s / question (median) | Calls / question | API errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 · one prompt | 61% | 60–62% | 83% | 57% | 60 | 100% | 0% | 1% | $0.00037 | 4.5 | 1.0 | 0 |
| 1 · routing | 58% | 58–58% | 83% | 55% | 60 | 100% | 0% | 3% | $0.00024 | 6.8 | 2.0 | 0 |
| 1h · routing + handoff | 59% | 57–63% | 78% | 55% | 60 | 100% | 0% | 3% | $0.00023 | 6.9 | 2.0 | 0 |
| 2 · parallel vote | 59% | 57–62% | 87% | 53% | 60 | 100% | 0% | 1% | $0.00055 | 8.3 | 4.0 | 0 |
| 3 · orchestrator-worker | 57% | 53–60% | 83% | 52% | 60 | 100% | 0% | 1% | $0.00037 | 10.8 | 3.0 | 0 |
| 4 · evaluator-optimizer | 61% | 58–63% | 92% | 58% | 60 | 100% | 0% | 0% | $0.00050 | 11.7 | 3.3 | 0 |
| 5 · free agent | 45% | 42–49% | 61% | 32% | 59 | 100% | 0% | 20% | $0.00028 | 4.9 | 1.4 | 1 |

Noise floor: one question is 1.7 points. Repeats of the same level moved by up to 7 points (level 5), so smaller gaps between levels are not clear effects.

| Level | Inside the pattern |
|---|---|
| 1h · routing + handoff | handed to the human 0%; right on the rest 59% |
| 2 · parallel vote | 2.8 of 3 writers agree with the winner |
| 3 · orchestrator-worker | 1.0 sub-questions on average |
| 4 · evaluator-optimizer | 1.16 rounds on average |
| 5 · free agent | 1.4 steps on average; cap hit 0% |

How the free agent worked (all repeats; API errors left out):

| Before answering, it | Answers | Right | SQL errors |
|---|---|---|---|
| answered at once | 137 of 179 (77%) | 48% | 20% |
| described a database first | 37 of 179 (21%) | 32% | 19% |
| ran SQL first | 5 of 179 (3%) | 60% | 20% |

What if the agent's `database.table` names had worked (offline rerun of its stored queries): 35 answers failed on the prefix, 29 of them would be right; right would be 61% instead of 45%, same answer 3/3 83% instead of 61%.

Workflow minus the free agent (level 5), in points:

| Level | Right | Same answer 3/3 |
|---|---|---|
| 0 · one prompt | +15 | +22 |
| 1 · routing | +13 | +22 |
| 1h · routing + handoff (a person helps) | +14 | +17 |
| 2 · parallel vote | +14 | +26 |
| 3 · orchestrator-worker | +11 | +22 |
| 4 · evaluator-optimizer | +16 | +31 |
