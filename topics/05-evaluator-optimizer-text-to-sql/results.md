# 05 · Results

Built by `python -m sqlloop.report` from the run files only. Do not edit by hand.
Levels: 0 · one prompt, 1 · AI grader reads, 2 · run it, 3 · AI grader sees rows, 0+ · bigger model, 4 · bigger model grades, reads, 5 · bigger model grades, sees rows.

## Main set (60 questions, 6 databases)

Repeats per level: 3. Fixed / broken are questions per repeat (average). PASS on wrong, false alarm and PASS is right are per graded round (levels 1 and 3 only).

| Level | Model | Right | Right, extra columns forgiven | First try right | Fixed | Broken | PASS on wrong | False alarm | PASS is right | Rounds | Cap hit | API errors | s / question | $ / question |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 54% | 61% | 54% | 0.0 | 0.0 | – | – | – | 1.00 | 0% | 0 | 5.2 | $0.00019 |
| 1 | gpt-6-luna | 54% | 61% | 54% | 0.0 | 0.3 | 87% | 3% | 54% | 1.08 | 1% | 0 | 10.9 | $0.00042 |
| 2 | gpt-6-luna | 56% | 62% | 54% | 1.0 | 0.0 | – | – | – | 1.06 | 1% | 0 | 6.3 | $0.00023 |
| 3 | gpt-6-luna | 52% | 59% | 53% | 0.3 | 1.0 | 81% | 7% | 53% | 1.13 | 2% | 0 | 12.2 | $0.00049 |
| 0+ | gpt-6.1-sol | 57% | 59% | 57% | 0.0 | 0.0 | – | – | – | 1.00 | 0% | 0 | 4.4 | $0.00168 |
| 4 | gpt-6-luna + gpt-6.1-sol grades | 52% | 58% | 52% | 0.0 | 0.0 | 90% | 1% | 52% | 1.06 | 0% | 0 | 8.4 | $0.00132 |
| 5 | gpt-6-luna + gpt-6.1-sol grades | 56% | 62% | 57% | 0.3 | 1.0 | 85% | 3% | 56% | 1.09 | 0% | 0 | 9.5 | $0.00150 |

Right, by difficulty:

| Level | simple | moderate | challenging |
|---|---|---|---|
| 0 | 72% | 49% | 42% |
| 1 | 72% | 49% | 39% |
| 2 | 78% | 49% | 42% |
| 3 | 72% | 49% | 31% |
| 0+ | 72% | 54% | 42% |
| 4 | 72% | 46% | 39% |
| 5 | 72% | 51% | 42% |

## Held-out set (60 questions, 5 other databases)

Repeats per level: 3. Fixed / broken are questions per repeat (average). PASS on wrong, false alarm and PASS is right are per graded round (levels 1 and 3 only).

| Level | Model | Right | Right, extra columns forgiven | First try right | Fixed | Broken | PASS on wrong | False alarm | PASS is right | Rounds | Cap hit | API errors | s / question | $ / question |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 59% | 62% | 59% | 0.0 | 0.0 | – | – | – | 1.00 | 0% | 0 | 5.4 | $0.00017 |
| 1 | gpt-6-luna | 58% | 62% | 58% | 0.0 | 0.3 | 94% | 14% | 57% | 1.11 | 1% | 0 | 11.4 | $0.00037 |
| 2 | gpt-6-luna | 61% | 64% | 59% | 1.3 | 0.0 | – | – | – | 1.04 | 0% | 0 | 5.9 | $0.00018 |
| 3 | gpt-6-luna | 59% | 61% | 57% | 2.0 | 0.7 | 82% | 11% | 59% | 1.17 | 0% | 0 | 13.2 | $0.00043 |
| 0+ | gpt-6.1-sol | 71% | 71% | 71% | 0.0 | 0.0 | – | – | – | 1.00 | 0% | 0 | 4.2 | $0.00191 |
| 4 | gpt-6-luna + gpt-6.1-sol grades | 59% | 62% | 59% | 0.7 | 0.7 | 94% | 8% | 59% | 1.08 | 0% | 0 | 8.2 | $0.00124 |
| 5 | gpt-6-luna + gpt-6.1-sol grades | 59% | 63% | 58% | 1.0 | 0.0 | 91% | 4% | 59% | 1.07 | 0% | 0 | 8.7 | $0.00129 |

Right, by difficulty:

| Level | simple | moderate | challenging |
|---|---|---|---|
| 0 | 70% | 52% | 58% |
| 1 | 72% | 49% | 58% |
| 2 | 70% | 57% | 58% |
| 3 | 72% | 52% | 56% |
| 0+ | 80% | 67% | 69% |
| 4 | 72% | 51% | 58% |
| 5 | 69% | 53% | 61% |

Total spent on this topic (all run files, smoke included): $3.83
