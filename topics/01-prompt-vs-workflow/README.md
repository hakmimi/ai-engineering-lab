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

_From real runs on 2026-11-08: 30 claims × 3 repeats per level, prompt caching on. Full table: [`results.md`](results.md)._

| Level | Decision right | Amount right | Doc problems caught | False doc alarms | Time / claim | Cost / claim |
|---|---|---|---|---|---|---|
| 0 (gpt-6-luna) | 100% | 100% | 100% | 0% | 3.0 s | $0.0001 |
| 1 | 76% | 89% | 72% | 0% | 3.6 s | $0.0001 |
| 2 | 60% | 80% | 33% | 28% | 5.0 s | $0.0004 |
| 3 | 59% | 81% | 33% | 31% | 6.2 s | $0.0005 |
| 0+ (gpt-6.1-sol) | 100% | 100% | 100% | 0% | 2.9 s | $0.0015 |

**Observations (DRAFT notes):**
- One big prompt on the small model was right every time. On this data there was nothing left for a workflow to fix.
- Every step we added made results worse, not better.
- The router often picked the right travel type but wrote it in the wrong tag, so the code read "unclear" and sent the claim to a person (14–20 of 90 runs per level).
- Each document checker sees one document alone and applied "names the insured" literally. Quotes and assessor reports name the car or the address, not the person, so it asked for documents that were fine (19–20 of 90).
- The workflow cost about 5× more and took about 2× longer. The bigger model cost about 15× more for the same 100%.

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
