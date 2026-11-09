# NN · <The reader's question, as the post title>

<!-- Voice: first person, simple words, short sentences. No AI polish ("delve", "crucial", "it's worth noting").
     Numbers only from results.md. Graphs, not tables, in "The results". -->

## How this started

So, I came across this article from <publisher>: [<title>](<url>). <What it shows, in one or two sentences.>

It made me wonder. <The real-world worry or curiosity.> <The question the article leaves open.>

The article doesn't say. So I tried to find out.

## What <publisher> claims, and what it implies

<The method in plain steps (a short numbered list is fine).>

<What it shows as results. Its own caveats, quoted.>

<What it implies if true, for someone using it.>

## My experiment

So I decided to take it a step further.

### The question

<One sentence, bold.>

### The data

<Where it comes from, who made the answer key, why it fits. Main set vs held-out set in plain words.>

### The process

<The levels, one line each.>

![<diagram alt text>](design/process-diagram.png)

## How I measure it

<Each KPI in plain words, one short paragraph or bullet each.>

**What the article suggests:** <...>

**What I expect:** <the author's guesses, written before the runs>

## The results

<One line: the headline answer.>

### 1 · <Finding as a short sentence>

![<alt>](charts/<chart>.svg)

<2-4 sentences: what the graph shows, and why it matters.>

### What I expected vs. what happened

- <guess> → <what happened>

## Key takeaways

- **<takeaway>.** <one or two sentences>

## Limitations

- **<limit>.** <one or two sentences>

**Data credit.** <dataset, authors, licence>. See [`data/NOTICE.md`](data/NOTICE.md).

## Technical walkthrough

### The data

- **Source:** <...>
- **The sets:** <...>

### The tools

| Tool | What it does here |
|---|---|
| <tool> | <role> |

### The process, step by step

1. <...>

### The evals

<What the offline tests check, and how many.>

### Lessons from building it

<Real mistakes caught before they skewed the numbers: what it was, what it would have done to the result, how it's guarded now.>

<details>
<summary><b>The folder and how to run it</b></summary>

```
NN-<slug>/
├── README.md           ← this page
...
```

</details>
