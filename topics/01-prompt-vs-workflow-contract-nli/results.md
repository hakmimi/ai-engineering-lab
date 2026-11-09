# Results

## Main set

30 NDAs from ContractNLI's dev split. Prompts may be tuned on these.

Not run yet.

## Test set (held out)

30 NDAs from ContractNLI's test split. No prompt was tuned on them.

Not run yet.

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow-contract-nli"
.venv\Scripts\python -m ndaflow.run --level 3 --dry-run                # cost estimate only
.venv\Scripts\python -m ndaflow.run --level 3 --repeats 3 --yes
.venv\Scripts\python -m ndaflow.run --level 3 --repeats 3 --yes --set test
.venv\Scripts\python -m ndaflow.report                                  # rewrites this file
```
