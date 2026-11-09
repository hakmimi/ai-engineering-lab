---
name: validate-article
description: Use when the owner shares an AI-engineering article (Anthropic cookbook or any other) to validate, test, or "do the same way as the other topics", or says "do the next article" from articles.md, in the ai-engineering-lab repo.
---

# Validate an article

## Overview

Each topic takes one article's claim, rebuilds the method on **real data with an answer key someone else wrote**, measures it with KPIs on a **main set (tuning allowed) and a held-out set (never tuned)**, and ends as a blog post. Same recipe every time, so every post has the same quality.

**Core principle:** numbers come only from real runs on data we did not label, and the owner decides the three things only they can decide.

## The three stops (never skip, even when told "just do it end to end")

| Stop | When | Ask |
|---|---|---|
| 🛑 1 | After reading the article | Which claims to test, small or full version |
| 🛑 2 | Design written | Approve design (data, sets, levels, KPIs, budget, the owner's guesses) **and** the publish date, and whether to publish without asking again |
| 🛑 3 | Before any paid run | Spot-check sheet: do the labels look right? |

"Go ahead, I'm away" covers everything **between** stops, not the stops. If the owner is away, prepare the stop and wait.
Publishing needs a yes too: asked once at 🛑 2. Without it, stop before step 11 and ask.

## Steps

Details, commands and checklists per step: `reference.md` (read it at step 1).

1. **Read the article.** Claims, shown results, its own caveats, what it does **not** measure. Find its code if any. → 🛑 1
2. **Find data** with a third-party answer key. Check the licence. Pin the version. Count what exists. No fit → tell the owner; never write the key yourself.
3. **Topic folder + design.** Number = next free one (check `topics/`, untracked folders in the main checkout, `articles.md`). Create **`topics/NN-<slug>/`** (slug = method + dataset, e.g. `06-table-retrieval-bird`) in the topic's worktree (step 4 commands), with `design/design.md` from `templates/design.md`. → 🛑 2
4. **Plan.** In the worktree `C:\Workshop\ai-engineering-lab-topicNN` (branch `topic-NN-<slug>`, made at step 3). Plan with superpowers:writing-plans; build with superpowers:executing-plans and TDD.
5. **Build** data → levels → runner → report. Use `shared/llm.py`, `shared/runs.py`, `shared/charts.py`.
6. **Fresh review** of the whole branch (opus subagent) **before any money is spent**. Fix with RED→GREEN tests.
7. **Spot check** from `templates/spot-check.md`: 10 + 10 main-set items. → 🛑 3
8. **Runs:** `--dry-run` → 5-item smoke run → full runs. Budget per command $1, topic ceiling $5.
9. **Report:** `results.md` + SVG charts, generated from run files only.
10. **README** from `templates/README.md`: the 8-block order, but a fresh hook and topic-specific headings every time, with "Lessons from building it".
11. **Publish:** `python -m shared.publish_post`, build the blog, push. Merge `--no-ff` to lab main, push, remove the worktree, mark `articles.md`.

## Honesty rules

- Rules, prompts and thresholds come from the **main set only**. A test enforces it where it can.
- The model never sees labels or answer fields. Ids are opaque. The key is a separate file.
- API failures, unreadable answers and "not reviewed" are counted apart, never as model mistakes.
- The owner's guesses are written **before** runs; misses are reported.
- If the model or setup differs from the article's, say so in Limitations.
- A run that didn't happen is "not run", never estimated.

## Red flags — stop

| Thought | Reality |
|---|---|
| "No public data fits, I'll label a small set myself" | That's topic 1's weak spot. Ask the owner. |
| "The owner said end to end, I'll approve the design myself" | Stops are the owner's. Prepare and wait. |
| "Small tweak after seeing held-out results" | That's tuning on held-out. Report as is, or make a new held-out set and say so. |
| "The review can wait until after the runs" | Topic 4's review found 3 bugs that changed numbers. Review first. |
| "I'll type the number into the README" | Copy from `results.md` only. |
