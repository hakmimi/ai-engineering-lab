# Results

Averages over repeats, from the latest run file of each level. Prompt caching was on at every level.

| Level | Model | Decision right | Amount right | Doc problems caught | False doc alarms | Seconds / claim | $ / claim | Calls / claim | Cached input | Errors / repeat |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | gpt-6-luna | 100% | 100% | 100% | 0% | 3.0 | $0.0001 | 1.0 | 100% | 0.0 |
| 1 | gpt-6-luna | 76% | 89% | 72% | 0% | 3.6 | $0.0001 | 1.7 | 61% | 0.0 |
| 2 | gpt-6-luna | 60% | 80% | 33% | 28% | 5.0 | $0.0004 | 4.4 | 17% | 0.0 |
| 3 | gpt-6-luna | 59% | 81% | 33% | 31% | 6.2 | $0.0005 | 4.9 | 8% | 0.0 |
| 0+ | gpt-6.1-sol | 100% | 100% | 100% | 0% | 2.9 | $0.0015 | 1.0 | 93% | 0.0 |

Run files:

- `level-0-20261108-211805.json`: 30 claims × 3 repeats
- `level-1-20261108-211933.json`: 30 claims × 3 repeats
- `level-2-20261108-212134.json`: 30 claims × 3 repeats
- `level-3-20261108-212403.json`: 30 claims × 3 repeats
- `level-0+-20261108-212514.json`: 30 claims × 3 repeats

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow"
.venv\Scripts\python -m claimsflow.run --level 3 --dry-run     # cost estimate only
.venv\Scripts\python -m claimsflow.run --level 3 --repeats 3 --yes
.venv\Scripts\python -m claimsflow.report                       # rewrites this file
```
