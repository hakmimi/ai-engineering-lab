# validate-article: step details

Paths: lab repo `C:\Workshop\ai-engineering-lab` (GitHub `hakmimi/ai-engineering-lab`), blog `C:\Workshop\Blog`
(Astro, `hakmimi/Blog`, live at https://hakmimi.github.io/Blog/). Python venv: `C:\Workshop\ai-engineering-lab\.venv`.
Owner preferences: simple words, short sentences, emoji blocks, one "Recommended", a yes/no question at the end.

## 1 · Read the article

- Fetch the page. If it's long, read it all (topic 4's design missed the last 5% and the band rounding was wrong).
- Look for its code (cookbook notebook, GitHub). The real logic (thresholds, prompts, formats) is often only there.
- Write down, for 🛑 1:

| What | Example |
|---|---|
| Claims (close to its words) | "Rules + Claude flag forbidden actions" |
| Shown results | "20 sessions, 4 flagged, $0.09" |
| Its own caveats, quoted | "worked examples, not an accuracy measurement" |
| What it does **not** measure | accuracy, false alarms, cost on new data |
| Can it be rebuilt? | method public? model available? data exists? |

- 🛑 1 message: the claims as a table, what you'd test, small vs full version (Recommended one), and "worth testing?" honestly.

## 2 · Find data

- Want: public, labelled by **someone else** (benchmark authors, code-checked end states, human annotators), licence that allows reuse, a size you can sample from.
- Pin it: git commit, dataset version, or download date + checksum. Count each label group on the pinned version.
- Raw data stays out of git (`data/raw/` in `.gitignore`). Built sets + `key.json` + `NOTICE.md` (citation, licence, what changed) are committed.

## 3 · Design (template: `templates/design.md`)

- **Levels:** 0 = no-model baseline (free), 1 = one naive prompt, 2 = the article's way. Add a level only if a claim needs it.
- **Sets:** split **before** drawing, seed 2026, so held-out has new items/sources/styles. ~30 per label group per set is enough for a small version.
- **KPIs:** one or two that answer the claim + errors kept apart + $ / seconds per item. 3 repeats for model levels.
- **Budget:** estimate tokens (chars ÷ 4) × calls × list price. Show it. Ceiling $5 per topic.
- **The owner's guesses:** ask for them at 🛑 2, write them in the design's "What I expect" line (one guess per KPI, a number where possible) before any run. The README's "What I expected vs. what happened" copies them.
- **Model:** the article's model if we can call it; otherwise the cheapest current model of the same tier, written in the design and the README's Limitations.
- 🛑 2 also asks: publish date (today or a scheduled day; posts are spread a few days apart) and "publish without asking again?".

## 4 · Worktree and plan

Made at step 3, so the topic folder and design live on the topic branch from the start:
```
git -C C:\Workshop\ai-engineering-lab worktree add -b topic-NN-<slug> ..\ai-engineering-lab-topicNN main
```

- Never build in the main checkout: other sessions may be working there. The only things done in the main checkout are the final merge and push (step 11), after `git status` shows nothing of yours is in the way.
- If the shared helpers (`shared/runs.py`, `shared/charts.py`, `shared/publish_post.py`) are not on main yet, cut the branch from the branch that has them.
- Add the topic's folder to `pyproject.toml` `pythonpath` and `testpaths`. (On merge, this file conflicts: keep every topic.)
- The worktree has no `.env`. For real runs, set `shared.llm.ENV_FILE = Path(r"C:\Workshop\ai-engineering-lab\.env")` in a small scratchpad launcher, or pass keys by env. Never print `.env`; never `source` it in bash.
- Plan: `design/plan.md` via superpowers:writing-plans. Execute inline via superpowers:executing-plans.

## 5 · Build

| Part | Notes |
|---|---|
| `build_data.py` | Reads the pinned raw data, writes sets with opaque ids and `key.json`. Records seed, source paths, skips. |
| levels | `llm_call(..., cached_system=SYSTEM, label=..., tracker=...)`, answers in XML tags, `extract_xml`. |
| runner | `--level --set --repeats --limit --budget --workers --yes --dry-run`. `shared.runs.spent_so_far` / `over_ceiling` / `save_run`. API exception → status "failed", error text saved. |
| report | `shared.runs.latest_run` (ignores smoke and partial runs) → `results.md` + `charts/*.svg` via `shared.charts.bar_chart`. |
| tests | `evals/`, offline, fake `llm_call`. Root `conftest.py` blocks real API calls and `.env`. |

Charts: horizontal bars, slots s1/s2/s3 in order, `muted` for a reference or chance series, every bar labelled, `ref=` for the article's number. Graphs, not tables, in the post.

Process diagram: `design/process-diagram.html` (one page, light/dark tokens), rendered to PNG:
```
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --screenshot=<abs path>\process-diagram.png --window-size=1040,1180 <abs path>\process-diagram.html
```

## 6 · Fresh review before spending

Dispatch an opus subagent with the branch diff, design and plan. Ask it to look for: anything built from held-out data, hidden fields the model can't see or labels it can, failures scored as misses, quotes or checks not recorded, missing noise floor, results not reproducible from run files. Fix Critical/Important with RED→GREEN tests.

## 7 · Spot check (🛑 3)

`spot-check.md`: 10 positives + 10 negatives from the main set (for many classes or a score: 20 items spread over the classes, or the 10 hardest + 10 easiest), each shown exactly as the model sees it. The owner marks ✓/✗. A ✗ that shows a class of bad items (topic 4: "say-only" attacks) → remove that class from all sets, redraw, note it in the README. Never edit single labels.

## 8 · Runs

1. Level 0 (free) on all sets.
2. `--dry-run` for each paid level → show the estimate.
3. `--limit 5` smoke run (first 5 items, 1 repeat) → check one run file by eye.
4. Full runs, 3 repeats. Stop at the budget; partial runs are marked and not reported.
Every paid command (smoke runs too) counts toward the $5 ceiling: `spent_so_far` sums all run files.
If a provider fails (no credit, outage), switching model is allowed **only if disclosed** in the README's tools table and Limitations.

## 9 · Report

`python -m <package>.report` writes `results.md` and `charts/`. Every number in the README is copied from `results.md`.

## 10 · README (template: `templates/README.md`)

Order (fixed): opening hook → the claim → the experiment → how it's scored → results (graphs; main, then held-out) → takeaways → limitations → technical walkthrough (data, tools, step by step, evals, lessons from building it, folder box in `<details>`).
**Wording is never reused:** a fresh opening line and topic-specific headings in every post. Posts that all start "So, I came across…" under "How this started" read as machine-made (the author, 2026-11-09).
Voice: first person, plain, a bit casual. No "delve", "crucial", "robust", "it's worth noting", no tricolons.

## 11 · Publish and finish

```
python -m shared.publish_post topics/NN-<slug> --slug NN-<short> --title "..." --description "..." \
    --date 2026-11-12T10:00:00+02:00 --tags a,b --code-blurb "It has ..." --source anthropic \
    --article "Anthropic|Article title|https://...|2026-10-16"
```
- `--article`: the article the post tests, `Publisher|Title|URL|YYYY-MM-DD` with the date **the article came out** (read it on the page). Repeat it for a second article. The blog shows it under the title and orders the Timeline page by it.
- **`--date` is the real day the post goes out**: never earlier than the work in git. Space posts about a week apart.
- `--source`: the article companies' logo keys (from the blog's `src/utils/sources.ts`, e.g. `anthropic`, `linkedin`, `pinterest`); the logo shows next to the title. Add a key there first for a new company.
- Code links point to `tree/main/...`, so **merge the lab first**: in the main checkout, `git merge --no-ff topic-NN-<slug>`, push.
- Blog: build check in PowerShell `node_modules\.bin\astro.cmd build` (no pnpm on PATH), commit, push. GitHub Actions deploys; a future `pubDatetime` appears on its day (daily rebuild 08:15 UTC).
- Remove the worktree (`git worktree remove`), delete the branch, set the row in `articles.md` to `published` with the date and post URL.
