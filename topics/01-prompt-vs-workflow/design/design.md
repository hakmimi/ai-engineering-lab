# Topic 1: Prompt vs Workflow — Design

Date: 2026-11-08
Folder: `topics/01-prompt-vs-workflow/` in `hakmimi/ai-engineering-lab`
Source article: Anthropic cookbook, "Basic Multi-LLM Workflows"
https://platform.claude.com/cookbook/patterns-agents-basic-workflows
Diagram: `process-diagram.html` in this folder (also at https://claude.ai/artifact/6LRttBAXp4bSDn4rHATJ5R, private to the owner)

## 1. Intent

This is the first topic of a public learning portfolio. Each topic takes one Anthropic article, rebuilds it on a different, realistic use case, and shows the trade-offs with real numbers.

The article shows three patterns (route, parallel, chain). It does not say when they are worth using. This topic answers that question:

> When is it worth splitting a job across several AI calls instead of one big prompt, and what does it cost?

The answer is a short guide ("use it when / skip it when") backed by measurements on one realistic business task. The point for a reader is that the author can judge when a pattern pays off and can prove it. Copying the patterns alone does not show that.

## 2. Use case: insurance claims intake

The author knows insurance from the inside. A claim arrives with a description, a policy number and attached documents. The system decides what happens to it.

Lines of business (decided):
- **Car, comprehensive.** Property damage only. Bodily injury is out of scope.
- **Home, water damage.**
- **Travel.** Two sub-types share one flow: medical (doctor, medicine, hospital) and trip cancellation. They have different required documents and caps, so **the router has four labels**: car, water damage, travel medical, travel cancellation (Claude's call). "Route correct" is scored on these four labels.

All policies, customers, claims and documents are **fully made up** (decided). No real insurer's wording or name is used.

## 3. The process (decided)

Three steps, one pattern each:

1. **Route.** Classify the claim as car, water damage or travel. Each type has its own required-document list and its own policy wording. If the type is unclear, the claim goes to a human handler.
   - **What the router sees (decided by the author):** the claim arrives with the **customer ID**, not a policy number. A customer can hold several policies (car, home, travel). The AI reads what happened and picks the claim type; plain code then looks up that customer's policy of that type.
   - **No matching policy** (for example water damage, but the customer has no home policy) → **decline: no coverage**.
   - **Unclear description** → **hand to a person**.
   - The test set includes a few claims of each kind. Level 0 has no route step but is allowed and expected to return these same decisions.
2. **Parallel: document check.** Plain code holds the required list for the claim type. For each required document, one AI call checks at the same time: is it attached, and is it the right one (the right kind of document, the insured's name, details that match the claim itself, such as the event date and amounts)? If any document is missing or wrong, the claim stops with "request documents" and a message naming exactly what is missing or wrong.
   - **Line between "request documents" and "decline" (Claude's call):** the document check only asks "is the paperwork complete and does it belong to this claim?". Whether the event date falls inside the policy period, and whether the driver was listed and old enough, are coverage and exclusion questions for step 3, so they lead to "decline", not "request documents".
3. **Chain: decide step by step.** Covered? → any exclusion? → how much? The first two are AI calls. The amount is **plain code** (recognized amount, cap, deductible, refund rate). Not covered or excluded goes straight to the result with the reason.
   - **Where the recognized amount comes from (decided by the author), one source per type:**

     | Claim type | Recognized amount |
     |---|---|
     | Car | Assessor's report |
     | Water damage | Assessor's report if there is one, otherwise the repair quote |
     | Travel medical | Receipts |
     | Travel cancellation | Paid in advance − supplier refunds |

   - An AI call reads these numbers (and network vs private provider) out of the documents and returns them as plain values; code then applies the policy terms. Whether that reading happens inside the "how much?" step or as part of the document check is left to the builder, as long as every level is scored the same way.

Every claim returns:
- **decision:** approve full, approve partial, decline with reason, request documents, or hand to a person (route unclear)
  - **"Partial" (Claude's call, matching normal claims practice):** subtracting the deductible does not make an approval partial. "Approve partial" means the insurer pays less than the recognized loss for another reason: a cap, a refund rate under 100% (for example a private provider), or part of the claim excluded.
- **amount** in ₪ (0 when declined or waiting for documents)
- **document status:** complete, or the list of missing or wrong documents
- **reason:** one or two plain sentences

Worked examples the data must support:
- Car: repair 12,000 ₪ − deductible 1,500 ₪ = pays 10,500 ₪.
- Home: quote 8,000 ₪ − deductible 1,000 ₪ = pays 7,000 ₪. Pipe corrosion is excluded.
- Travel cancellation: paid 10,000 ₪ − supplier refunds 3,000 ₪ = loss 7,000 ₪, cap 5,000 ₪ → pays 5,000 ₪.

## 4. The experiment (decided)

The same claims run through increasing levels:

| Level | How the claim is handled |
|---|---|
| 0 | One big prompt: all three policy wordings, the customer's schedule, the claim and its documents → full result in one call |
| 1 | Add step 1: route first, then one prompt per claim type that holds only that type's policy |
| 2 | Add step 2: the parallel document check before the decision prompt |
| 3 | Add step 3: the chain (covered → exclusion → code computes the amount) |
| 0+ | Level 0 again on a larger model (bonus: is a smarter single call as good as a workflow of cheaper calls?) |

Measured per level:
- decision correct (vs the answer key)
- amount exactly right (to the shekel)
- document problems caught (missing or wrong), and false alarms
- time per claim (wall clock)
- tokens, number of calls and cost in $ per claim

The deliverable of the experiment is `results.md`: one table across levels, plus a few lines of plain observation. The "use it when / skip it when" guide is derived from that table.

## 5. Test data (decided, with author review)

- **3 policy wordings**, 1–2 pages each: covered events, exclusions, caps, deductibles, refund rates, network vs private provider rules.
- **Customer schedules**: policy number, holder name, line, active dates, add-ons bought, deductible, listed drivers and minimum driver age (car).
- **About 30 claims**, roughly 10 per line, each with a known right answer. About a third are tricky on purpose: policy not active on the date, unlisted or underage driver, pipe corrosion, cancellation reason not covered, loss over the cap, a missing document, a wrong document (receipt instead of a police report, wrong name, date outside the policy).
- **Documents are short text files** standing in for the real document (an assessor's report as text, a receipt as text). No images or PDFs.
- **Answer key** per claim: claim type, document status, decision, amount, reason.
- **Claude drafts the data; the author reviews and corrects the answer key before any measured run.** The author's insurance knowledge is what makes the key trustworthy.

## 6. How it gets made

Decided:
- Python, using Anthropic's official Python SDK.
- A shared helper in `shared/`: `llm_call` (prompt in, text out), `extract_xml` (as in the article), and per-call tracking of latency and input/output tokens.
- The API key is read from `ANTHROPIC_API_KEY` in the repo's `.env` file (exists, git-ignored, filled in by the author). The key is never printed, logged or committed.
- Tests run without network by replacing `llm_call` with a fake.
- The code lives in the public repo. Commits are local; pushing happens only when the author asks.

Claude's calls (the author can change them):
- **Models:** levels 0–3 use one small, cheap current model (`claude-haiku-5-5`). Level 0+ uses a larger one (`claude-opus-5-5`). Both are set by environment variables.
- **Repeats:** every level runs the full claim set 3 times; results report the average, so one lucky or unlucky run doesn't decide the outcome.
- **Budget:** the whole experiment should cost a few dollars. The runner prints an estimated cost before it starts and stops if the estimate is over $10.
- **Folder layout:** the earlier plan had `quick_setup/` and `better_version/`. This topic uses the levels instead: level 0 is the "quick" version and level 3 is the "better" one.
- **Concurrency for step 2:** a thread pool like the article's `parallel()`.
- **Prompt caching:** on, and used the same way at every level (cache the policy wordings and other fixed text). Production systems would cache, so leaving it off would make level 0 look worse than it really is. `results.md` states that caching was on and shows cached vs uncached tokens.

## 7. Goals, non-goals, anti-goals

Goals:
- Show, with numbers, when each pattern pays off on a realistic task.
- Keep each pattern's job obvious: route sorts, parallel checks documents, chain decides.
- Show that AI reads and judges while plain code does the math.
- Make the code small enough that a reader can follow it in one sitting.

Non-goals (left out on purpose; possible "better version" ideas for later):
- Splitting a claim into damage components (pipe, wall, cabinet).
- Referral to an assessor or investigator, and suspicion or fraud scoring.
- The wait-and-recheck loop after documents arrive. The claim simply stops and says what is missing.
- Bodily injury, subrogation (recovering money from the other side), live emergency help abroad, actual payment.
- Searching large document libraries (RAG). Policies are short and go straight into the prompt.
- Any user interface.

Anti-goals (would make this a failure even if it runs):
- Invented or "estimated" results. If a run did not happen, `results.md` says so.
- Polished, AI-sounding prose in the README or blog post. Claude writes short draft notes only; the author writes the final text in their own voice.
- Using who a person is (age, origin, gender) as a suspicion signal.
- Real insurer documents, names or branding.
- Over-building: agents, frameworks, databases or extra patterns beyond the three.

## 8. Deliverables

In `topics/01-prompt-vs-workflow/`:
- `README.md` (exists as a skeleton): the topic's front page. It explains what we tried (question, use case, the three steps, the levels) and what we found (the results table, observations, "use it when / skip it when", caveats, what is left for a better version). The "found" sections are filled only from real runs. Text stays short draft notes for the author to rewrite.
- `data/`: policy wordings, schedules, claims, documents, answer key.
- The code for levels 0, 1, 2, 3 and 0+, and one runner that scores them against the answer key.
- `evals/`: offline tests.
- `results.md`: the measured table, filled only from real runs.

The blog post itself (in the separate `Blog` repo) is a later step, written by the author.

## 9. Left to the builder

- Exact prompt wording, and whether answers come back as XML tags (the article's style) or JSON.
- File formats for data and answer key.
- Module and file names inside the topic folder.
- How the runner prints progress.
