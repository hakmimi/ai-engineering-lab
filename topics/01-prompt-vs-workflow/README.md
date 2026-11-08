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

### Hard set (held-out)

30 new claims no prompt was tuned on ([`design/hard-set.md`](design/hard-set.md)): longer documents, extra attachments, sums, numbers that conflict, facts buried in text. Answer key reviewed by the author before the run; after it, the author ruled the burst water heater itself is not covered (H-WAT-01), and scores were re-computed from the saved runs.

| Level | Decision right | Amount right | Doc problems caught | False doc alarms | Time / claim | Cost / claim |
|---|---|---|---|---|---|---|
| 0 (gpt-6-luna) | 94% | 93% | 89% | 4% | 3.5 s | $0.0002 |
| 1 | 94% | 94% | 89% | 6% | 5.4 s | $0.0002 |
| 2 | 76% | 83% | 67% | 25% | 6.6 s | $0.0005 |
| 3 | 70% | 80% | 67% | 30% | 7.7 s | $0.0006 |
| 0+ (gpt-6.1-sol) | 96% | 96% | 100% | 1% | 3.0 s | $0.0018 |

**Observations (DRAFT notes):**
- Now one prompt on the small model does fail (94%): once it missed a call-up dated before the booking, and every time it asked for new receipts when one was a friend's (every small-model level did that).
- Routing alone (level 1) did not help or hurt. It still caught both traps (a flooded car, a home flood after a holiday).
- The narrow document checks hurt most. Each sees one document and takes the claim at its word: a parked car "has no driver" so the license is "wrong"; the claimed amount is the net loss, so the receipts "do not match"; photos of an engine with no outside damage "show no damage".
- Level 3's math code cannot say "partial because part is excluded" (a visit after the trip), so it declined that claim every time.
- The bigger single model was the best and the fastest: 96%, at about 9× the small model's cost and 3× the full workflow's. Its one repeated miss: it paid for the burst water heater itself, which the wording does not cover.

## When to use it, when not to

_DRAFT notes from the runs above. Rewrite in your own words._

| Option | Use it when… | Skip it when… |
|---|---|---|
| One big prompt | All the rules and documents fit in one prompt and the model can read them together. Here it was the most accurate on the small model (100% main, 94% hard), the cheapest and the fastest. | It starts missing things you can name and test. Then try a bigger model first: here that was one change and still the fastest option. |
| Route | Each type needs very different rules, or the full rule set is too long for one prompt. It cost almost nothing extra and kept accuracy (99% / 94%). | Everything already fits in one prompt: it adds a call and one more answer to read without adding accuracy. Read its answer forgivingly, or a wrong tag sends good claims to a person (76% on the first try). |
| Parallel | The checks are truly independent and each one fits in one short rule, or speed across many documents matters. | A check needs the rest of the claim to judge it. A checker that sees one document took the claim word for word: a parked car "has no driver", the net claim "doesn't match" the receipts (25–30% false alarms on the hard set). |
| Chain | You need to show each step, or the math must be exact and auditable, so code does it. Amounts were rarely the problem. | A step needs facts another step owns (the "covered?" step could not see when the policy was bought), or the outcome has a case the code cannot express ("partial because part is excluded"). |

**In one line (DRAFT):** start with one prompt and a small test set with an answer key; split only the step you can show is failing, and measure again.

## Caveats

_DRAFT notes._

- Made-up data: 3 short policy wordings, 30 + 30 claims. Real files are longer and messier.
- One model family (OpenAI gpt-6-luna and gpt-6.1-sol), 3 repeats per level.
- The workflow prompts were fixed once, on the main set. The hard set was never tuned on; its numbers are the fairer ones.
- The answer key is one expert's reading. One claim (the water heater) could be read two ways; the author ruled after the run and scores were re-computed, not re-run.
- Prompt caching was on everywhere, which helps the long single prompt most.
- Costs are tiny here (under $0.002 per claim at every level). The 3–5× cost and 2× time of the workflow matter more at real volume.

## Left for a better version

- A fixed answer format from the API (structured output) instead of reading tags
- Document checks that see the whole claim, or one check for all documents
- Let the chain say "partial because part is excluded"
- Split a claim into damage components (pipe, wall, cabinet)
- Refer to an assessor or investigator
- Wait for missing documents, then re-check
- Search large policy libraries (RAG)

## Folder map

```
01-prompt-vs-workflow/
├── README.md        ← this file
├── design/          ← design document and process diagram
├── claimsflow/      ← the code: levels 0–3, runner, scoring, report
├── data/            ← made-up policies, customers, claims, answer key (hard/ = held-out set)
├── evals/           ← offline tests
└── results.md       ← measured results (real runs only)
```
