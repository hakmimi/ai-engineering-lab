# 01 · Prompt vs Workflow

> DRAFT. Rewrite in your own words before publishing.

**Question:** when is it worth splitting a job across several AI calls instead of one big prompt, and what does it cost?

**Source:** Anthropic cookbook, [Basic Multi-LLM Workflows](https://platform.claude.com/cookbook/patterns-agents-basic-workflows) (route, parallel, chain).

## What we tried

**Use case:** insurance claims intake. A claim arrives and the system decides what happens to it. Three lines of business, all made up: car comprehensive, home water damage, travel (medical and cancellation).

**The workflow, one pattern per step** (diagram: [`design/process-diagram.html`](design/process-diagram.html)):

1. **Route:** what kind of claim is it?
2. **Parallel:** check all required documents at once. Is each one there, and is it the right one?
3. **Chain:** covered? → any exclusion? → how much? The AI decides; plain code does the math.

**The comparison.** The same claims run through increasing levels:

| Level | How the claim is handled |
|---|---|
| 0 | One big prompt |
| 1 | + Route |
| 2 | + Parallel document check |
| 3 | + Chain, code does the math |
| 0+ | One big prompt on a larger model |

**Scored on:** decision right · amount right · document problems caught · time · cost.

## What we found

_Not run yet. This section is filled only from real runs in [`results.md`](results.md)._

| Level | Decision right | Amount right | Doc problems caught | Time / claim | Cost / claim |
|---|---|---|---|---|---|
| 0 | – | – | – | – | – |
| 1 | – | – | – | – | – |
| 2 | – | – | – | – | – |
| 3 | – | – | – | – | – |
| 0+ | – | – | – | – | – |

**Observations:** _to fill after the runs_

## When to use it, when not to

_To fill after the runs._

| Option | Use it when… | Skip it when… |
|---|---|---|
| One big prompt | | |
| Route | | |
| Parallel | | |
| Chain | | |

## Caveats

_To fill: what broke, what surprised us, and the limits of this test (made-up data, 30 claims, one model family)._

## Left for a better version

- Split a claim into damage components (pipe, wall, cabinet)
- Refer to an assessor or investigator
- Wait for missing documents, then re-check
- Search large policy libraries (RAG)

## Folder map

```
01-prompt-vs-workflow/
├── README.md        ← this file
├── design/          ← design document and process diagram
├── data/            ← made-up policies, customers, claims, answer key
├── evals/           ← offline tests
└── results.md       ← measured results (real runs only)
```
