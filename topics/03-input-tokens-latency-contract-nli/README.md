# 03 · Fewer input tokens, faster answers? Real contracts, OpenAI models

## Why I did this

Anthropic's [latency article](https://platform.claude.com/cookbook/latency-optimization-latency-optimization#input-token-management) says input tokens cost time: the model reads every token before it writes the first word. Its "input token management" section tests four levers (smaller prompts, prompt caching, pre-warming, message threads) and gives numbers for each. Those numbers are for Claude, on a made-up insurance desk, on Anthropic's own network.

So: **are these general rules about input tokens, or Claude facts? Same claims, real NDAs (topic 2's), OpenAI models, my home connection.**

## Spoiler alert: the bottom line

**On OpenAI, from my home connection, the input-token levers saved money and bytes, not seconds.** Caching cut the cost of a chat by 80–85% and the server-side conversation cut each upload from 397 KB to 1.3 KB, but the first word didn't come sooner. Reading the prompt took about 0.4 s per 100K tokens on the small model, which is smaller than the normal swings of the network and the API.

| Claim | Article (Claude) | Me (OpenAI, home connection) | Holds? |
|---|---|---|---|
| A bigger prompt = a slower first word | +0.25 s per 100K tokens | small model +0.39 s, large model **+1.04 s** per 100K | **Yes**, and more on the large model |
| Caching cuts cost | −85% | −80% (1 NDA), **−85%** (30 NDAs) | **Yes** |
| Caching speeds up a long prompt | turn 2: 1.7 s → 0.5 s | 1.20 s off, 1.56 s on (no gain) | **No** |
| Pre-warming speeds up the first turn | 1.0 s → 0.8 s | 1.31 s cold, 1.64 s warmed (no gain, 10/10 cache hits) | **No** |
| Server keeps the chat | 1.27 s → 0.63 s, 22.3 MB → 0.3 KB | **397 KB → 1.3 KB**, 1.14 s → 1.06 s (within noise) | **Bytes yes, speed no** |

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

A legal team keeps a pack of NDAs open and asks one question per chat turn: "Contract C07: may the receiving party share the information with its employees?" The model answers with a label (says it / says the opposite / not mentioned) and the sentence numbers that prove it, so every answer can be checked against the lawyers' labels.

The contracts are the big, fixed part of the prompt; the questions are small and change every turn. That is exactly the shape where caching, pre-warming and a server-side conversation should help.

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

```
design/          design.md (what and why), plan.md (how it was built)
ndaspeed/
  config.py      models, paths, the topic's $10 ceiling
  timer.py       one streamed call, timed event by event (first word, total, tokens, bytes)
  packs.py       contract packs, questions, prompt text, answer reading
  chat.py        one 17-turn chat, three ways: cache on, cache off, previous_response_id
  experiments.py the five tests (0-4)
  stats.py       median, p90, slope, bootstrap interval
  cost.py        cost per call, budget stop
  run.py         CLI: estimate, budget check, run, save the run file
  report.py      writes results.md from the run files
evals/           offline tests (a fake client, no network)
runs/            raw run files (git-ignored)
results.md       generated
```

The NDAs, statements and answer key are read from topic 2's `data/` folder; nothing is copied.

## How to run

From the repo root (PowerShell):

```powershell
$env:PYTHONPATH = ".;topics/01-prompt-vs-workflow-contract-nli;topics/03-input-tokens-latency-contract-nli"
.venv\Scripts\python -m ndaspeed.run --test 1 --dry-run           # cost estimate only, nothing sent
.venv\Scripts\python -m ndaspeed.run --test 1 --model both --yes  # a real run (tests 0-4, one at a time)
.venv\Scripts\python -m ndaspeed.report                           # rewrites results.md
```

## What I found

All numbers are medians from `results.md`; "first word" is the time to the first answer text.

- **The network floor is about 0.9 s** (p90 1.8 s) for a tiny prompt, twice the article's floor. Single calls sometimes took 4–10 s for no reason in the request.
- **Prompt size (test 1):** the large model (`gpt-6.1-sol`) went from 1.5 s at 20K tokens to 2.8 s at 151K: **+1.04 s per 100K**, four times the article's number. The small model (`gpt-6-luna`) gave +0.39 s per 100K, but its runs were noisy (one 100K call took 9.7 s).
- **Caching (test 2):** cost per 17-turn chat on the 30-NDA pack fell from $0.135 to $0.021 (**−85%**), with ~94% of input read from cache. The first word did not get faster: turns 2–17 were 1.20 s without and 1.56 s with the cache (interval −0.06 to +1.05 s). On the 1-NDA chat, cache-on was even a little slower (+0.12 s, interval +0.01 to +0.24 s). I don't know why; a guess is that `prompt_cache_key` sends a whole chat to one machine.
- **Pre-warming (test 3):** after the fix below, every warmed question read the pack from cache (10/10), and was still not faster (1.31 s cold, 1.64 s warmed; interval −1.29 to +1.16 s).
- **Server-side conversation (test 4):** `previous_response_id` cut each request from 397 KB to 1.3 KB, and the first word stayed the same (1.14 s → 1.06 s; interval −0.21 to +0.18 s). 0.4 MB of text is nothing for a home upload link; the article's win came from 22 MB of images.
- **Accuracy stayed level across variants** (label right 60–80%, no variant consistently ahead). 7 of 442 answers in test 2 broke the answer format and count as wrong.

**Gotchas the runs caught:**
- **OpenAI hit the cache only when a new prompt started with the whole earlier prompt.** My first warm-up ended with "Reply with OK.", so it never helped (0/10 hits). A warm-up must send the shared start and nothing after it.
- **A re-run with the same seed reused last run's "random" first lines,** and OpenAI still had them cached 8 minutes later. The report's cold check caught it; each run now adds its own random part.
- **Thinking costs more time than reading.** At reasoning effort "low" the small model sometimes thought for 30–340 tokens, adding 0.5–4 s. All tests ran at the lowest effort each model accepts ("none" on `gpt-6-luna`, "low" on `gpt-6.1-sol`).
- **Re-sending an 80K-token chat every turn hit the 2M tokens-per-minute limit** 4 times in test 4 (retried outside the clock).

**Total spend: about $3.55** (run files $3.46, plus ~$0.09 of diagnosis calls).

## Caveats

- **One machine, one home connection, one day.** Network noise is part of what I measured; from a cloud machine the reading time would stand out more.
- **OpenAI, not Claude.** The levers are close, not the same (automatic caching, no zero-token warm-up, `previous_response_id` instead of message threads).
- **Caching and pre-warming ran on the small model only** (cost). The large model reads slower (+1 s per 100K), so that's where caching could show a speed-up.
- **Small samples:** 5 + 3 rounds in test 1, 10 + 3 chats in test 2, 10 repetitions in test 3, 3 chats in test 4.
- **The long pack is 79K tokens,** not the article's 146K; 60 NDAs reach 151K at most.
- **Thinking was off on the small model,** so its labels (60–80% right) are lower than topic 2's 82%. Accuracy here is a guard rail between variants, not a score.
- **One cold request in the test 3 re-run stalled for about two hours** (the connection hung). Medians ignore it; it shows why the report uses medians.
