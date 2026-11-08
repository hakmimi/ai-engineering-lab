# Results

## Main set

Averages over repeats, from the latest run file of each level. Prompt caching was on at every level.

| Level | Model | Decision right | Amount right | Doc problems caught | False doc alarms | Seconds / claim | $ / claim | Calls / claim | Cached input | Errors / repeat |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 100% | 100% | 100% | 0% | 3.0 | $0.0001 | 1.0 | 100% | 0.0 |
| 1 | gpt-6-luna | 99% | 99% | 100% | 0% | 4.2 | $0.0001 | 1.9 | 91% | 0.0 |
| 2 | gpt-6-luna | 96% | 97% | 72% | 0% | 5.9 | $0.0004 | 5.3 | 33% | 0.0 |
| 3 | gpt-6-luna | 94% | 97% | 78% | 0% | 7.8 | $0.0005 | 6.1 | 16% | 0.0 |
| 0+ | gpt-6.1-sol | 100% | 100% | 100% | 0% | 2.9 | $0.0015 | 1.0 | 93% | 0.0 |

Run files:

- `level-0-20261108-211805.json`: 30 claims × 3 repeats
- `level-1-20261108-213509.json`: 30 claims × 3 repeats
- `level-2-20261108-213739.json`: 30 claims × 3 repeats
- `level-3-20261108-214041.json`: 30 claims × 3 repeats
- `level-0+-20261108-212514.json`: 30 claims × 3 repeats

## Hard set

Held-out claims (`data/hard/`): longer documents, extra attachments, sums and conflicting numbers. No prompt was tuned on them.

Averages over repeats, from the latest run file of each level. Prompt caching was on at every level.

| Level | Model | Decision right | Amount right | Doc problems caught | False doc alarms | Seconds / claim | $ / claim | Calls / claim | Cached input | Errors / repeat |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 94% | 93% | 89% | 4% | 3.5 | $0.0002 | 1.0 | 92% | 0.0 |
| 1 | gpt-6-luna | 94% | 94% | 89% | 6% | 5.4 | $0.0002 | 2.0 | 69% | 0.0 |
| 2 | gpt-6-luna | 76% | 83% | 67% | 25% | 6.6 | $0.0005 | 5.5 | 23% | 0.0 |
| 3 | gpt-6-luna | 70% | 80% | 67% | 30% | 7.7 | $0.0006 | 6.2 | 17% | 0.0 |
| 0+ | gpt-6.1-sol | 96% | 96% | 100% | 1% | 3.0 | $0.0018 | 1.0 | 92% | 0.0 |

Run files:

- `level-0-20261108-220300.json`: 30 claims × 3 repeats
- `level-1-20261108-220508.json`: 30 claims × 3 repeats
- `level-2-20261108-220744.json`: 30 claims × 3 repeats
- `level-3-20261108-221047.json`: 30 claims × 3 repeats
- `level-0+-20261108-221200.json`: 30 claims × 3 repeats

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow"
.venv\Scripts\python -m claimsflow.run --level 3 --dry-run     # cost estimate only
.venv\Scripts\python -m claimsflow.run --level 3 --repeats 3 --yes
.venv\Scripts\python -m claimsflow.run --level 3 --repeats 3 --yes --set hard
.venv\Scripts\python -m claimsflow.report                       # rewrites this file
```
