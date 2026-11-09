# 03 · Fewer input tokens, faster answers? Real contracts, OpenAI models

## Why I did this

<!-- NOTES for the author (rewrite in your own voice, then delete):
- Anthropic's latency article says input tokens cost time: the model reads every token before it writes the first word.
- Its "input token management" section tests four levers: smaller prompts, prompt caching, pre-warming, message threads.
- Its numbers are for Claude, on a made-up insurance desk, on Anthropic's own network.
- So: are these general rules about input tokens, or Claude-only facts? Same claims, real NDAs (topic 2's), OpenAI models, my home connection.
-->

## Spoiler alert: the bottom line

Not run yet. This section is written from `results.md` after the full runs.

## What I did

- **Took the article's four claims** from the "Input token management" section, with its numbers.
- **Found the OpenAI version of each lever** (automatic caching, a small warm-up request, `previous_response_id`).
- **Used topic 2's real NDAs** as the thing being read: a "contract pack" at the start of the prompt, one question per chat turn.
- **Checked every answer** against the lawyers' labels, so "faster" can't hide "worse".

| Test | Article's claim | What changes |
|---|---|---|
| **0** | (baseline) | Nothing: a tiny prompt, to see our network floor |
| **1** | A bigger prompt = a slower first word (+0.25 s per 100K tokens) | Prompt size: 20K / 50K / 100K / 180K tokens, never cached |
| **2** | Caching cuts cost a lot, but speed only for long prompts | Cache-friendly vs cache-busting prompt, on 1 NDA and on a 30-NDA pack |
| **3** | Pre-warming saves ~0.2 s on the first turn | Cold first question vs one after a warm-up call |
| **4** | Server-side conversation cuts upload time | Re-send the whole chat vs `previous_response_id` |

## The use case: an NDA desk

<!-- NOTES for the author:
- A legal team keeps a pack of NDAs open and asks one question per turn ("Contract C07: may it share with employees?").
- The contracts are the big, fixed part; the questions are small and change. That is exactly the shape where caching should help.
-->

**Data credit.** The contracts and labels come from **ContractNLI** (Koreeda & Manning, 2021, [stanfordnlp.github.io/contract-nli](https://stanfordnlp.github.io/contract-nli/)), released under **CC BY 4.0**, taken from topic 2's data folder.

## KPIs and success metrics

| Metric | What it means |
|---|---|
| **First word (TTFT)** | Seconds from sending the request to the first word of the answer (p50 = typical, p90 = slow tail) |
| **Total time** | Seconds until the answer is complete |
| **Slope** | Extra first-word seconds for every 100K more input tokens |
| **Cached share** | How much of the input was read from cache |
| **$ per chat** | What a 17-question chat costs |
| **Label right / evidence found** | Answer quality, against the lawyers' labels |

## What's in the folder

<!-- filled in when the code exists -->

## What I found

Not run yet.

## Caveats

<!-- NOTES: one machine, one home connection, one week; OpenAI's versions of the levers are close to Claude's, not the same. -->
