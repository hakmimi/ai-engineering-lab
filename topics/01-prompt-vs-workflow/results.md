# Results

Not run yet.

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow"
.venv\Scripts\python -m claimsflow.run --level 3 --dry-run     # cost estimate only
.venv\Scripts\python -m claimsflow.run --level 3 --repeats 3 --yes
.venv\Scripts\python -m claimsflow.report                       # rewrites this file
```
