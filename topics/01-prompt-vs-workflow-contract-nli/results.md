# Results

## Main set

30 NDAs from ContractNLI's dev split. Prompts may be tuned on these.

Averages over repeats, from the latest run file of each level. 17 statements per contract. Prompt caching was on at every level.

| Level | Model | Label right | F1 entailment | F1 contradiction | Evidence found | Evidence precision | Seconds / contract | $ / contract | Calls / contract | Cached input | Errors / repeat |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 83% | 0.86 | 0.59 | 56% | 72% | 21.3 | $0.0013 | 1.0 | 67% | 0.0 |
| 1 | gpt-6-luna | 82% | 0.86 | 0.58 | 62% | 67% | 42.1 | $0.0019 | 2.0 | 57% | 0.0 |
| 2 | gpt-6-luna | 78% | 0.82 | 0.57 | 54% | 72% | 23.2 | $0.0024 | 14.4 | 40% | 0.3 |
| 3 | gpt-6-luna | 78% | 0.82 | 0.55 | 59% | 63% | 28.0 | $0.0031 | 27.4 | 29% | 0.0 |
| 0+ | gpt-6.1-sol | 80% | 0.87 | 0.56 | 72% | 59% | 9.3 | $0.0090 | 1.0 | 67% | 0.0 |

Run files:

- `level-0-20261109-090048.json`: 30 contracts × 3 repeats
- `level-1-20261109-091550.json`: 30 contracts × 3 repeats
- `level-2-20261109-091135.json`: 30 contracts × 3 repeats
- `level-3-20261109-091229.json`: 30 contracts × 3 repeats
- `level-0+-20261109-085803.json`: 30 contracts × 3 repeats

## Test set (held out)

30 NDAs from ContractNLI's test split. No prompt was tuned on them.

Averages over repeats, from the latest run file of each level. 17 statements per contract. Prompt caching was on at every level.

| Level | Model | Label right | F1 entailment | F1 contradiction | Evidence found | Evidence precision | Seconds / contract | $ / contract | Calls / contract | Cached input | Errors / repeat |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 82% | 0.86 | 0.63 | 61% | 73% | 21.3 | $0.0013 | 1.0 | 67% | 0.0 |
| 1 | gpt-6-luna | 81% | 0.85 | 0.62 | 65% | 66% | 41.2 | $0.0019 | 2.0 | 57% | 0.0 |
| 2 | gpt-6-luna | 77% | 0.80 | 0.62 | 55% | 69% | 21.4 | $0.0024 | 14.4 | 27% | 0.0 |
| 3 | gpt-6-luna | 76% | 0.79 | 0.59 | 59% | 58% | 25.6 | $0.0032 | 27.5 | 28% | 0.3 |
| 0+ | gpt-6.1-sol | 81% | 0.88 | 0.61 | 76% | 58% | 9.4 | $0.0091 | 1.0 | 67% | 0.0 |

Run files:

- `level-0-20261109-092043.json`: 30 contracts × 3 repeats
- `level-1-20261109-092442.json`: 30 contracts × 3 repeats
- `level-2-20261109-092041.json`: 30 contracts × 3 repeats
- `level-3-20261109-092125.json`: 30 contracts × 3 repeats
- `level-0+-20261109-091815.json`: 30 contracts × 3 repeats

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow-contract-nli"
.venv\Scripts\python -m ndaflow.run --level 3 --dry-run                # cost estimate only
.venv\Scripts\python -m ndaflow.run --level 3 --repeats 3 --yes
.venv\Scripts\python -m ndaflow.run --level 3 --repeats 3 --yes --set test
.venv\Scripts\python -m ndaflow.report                                  # rewrites this file
```
