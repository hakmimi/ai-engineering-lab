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

_From real runs on 2026-11-08: 30 claims × 3 repeats per level, prompt caching on. Full table: [`results.md`](results.md). "First try" numbers are from commit be6ed1d._

| Level | Decision right | Amount right | Doc problems caught | False doc alarms | Time / claim | Cost / claim |
|---|---|---|---|---|---|---|
| 0 (gpt-6-luna) | 100% | 100% | 100% | 0% | 3.0 s | $0.0001 |
| 1, first try | 76% | 89% | 72% | 0% | 3.6 s | $0.0001 |
| 2, first try | 60% | 80% | 33% | 28% | 5.0 s | $0.0004 |
| 3, first try | 59% | 81% | 33% | 31% | 6.2 s | $0.0005 |
| 1, fixed | 99% | 99% | 100% | 0% | 4.2 s | $0.0001 |
| 2, fixed | 96% | 97% | 72% | 0% | 5.9 s | $0.0004 |
| 3, fixed | 94% | 97% | 78% | 0% | 7.8 s | $0.0005 |
| 0+ (gpt-6.1-sol) | 100% | 100% | 100% | 0% | 2.9 s | $0.0015 |

**The two fixes:** the router answer is read even when the label sits in the wrong tag; each document check gets a one-line rule for how that document is matched to the claim (car, address, supplier), instead of "it must name the insured".

**Observations (DRAFT notes):**
- One big prompt on the small model was right every time. On this data no workflow beat it, even after fixing.
- The first try of the workflow was much worse (59–76%). Both causes were in the glue, not the patterns: a reader that broke on a wrong tag, and a rule each narrow checker took word for word.
- After fixing, the workflow came close (94–99%) but still made new mistakes one prompt didn't: a narrow "is it covered?" step declined two cancellations because it could not see when the policy was bought.
- My cancellation-proof rule let a parent's own letter pass as proof of a child's illness (CAN-07). Each narrow rule is one more thing to get right.
- The workflow cost about 5× more and took about 2.5× longer. The fixes were tuned on these same 30 claims, so the "fixed" numbers are a best case.

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
