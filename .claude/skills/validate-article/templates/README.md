# NN · <The reader's question, as the post title>

<!-- The ORDER below is fixed. Every heading and the opening line are placeholders: write NEW, topic-specific ones
     for each post (e.g. "Two companies, one claim"). Never reuse "How this started", "So, I came across…",
     "What X claims, and what it implies", or generic headings like "My experiment" / "The results" / "Key takeaways".
     Voice: first person, simple words, short sentences. No AI polish ("delve", "crucial", "it's worth noting").
     Numbers only from results.md. Graphs, not tables, in the results. -->

<1 · Opening hook, no heading or a topic-specific one: a concrete moment or question from this topic, then the article link
and what it shows. Fresh wording every post.>

## <2 · The claim, as a topic-specific heading>

<The method in plain steps (a short numbered list is fine).>

<What it shows as results. Its own caveats, quoted.>

<What it implies if true, for someone using it.>

## <3 · The experiment, topic-specific heading>

### <The question>

<One sentence, bold.>

### <The data>

<Where it comes from, who made the answer key, why it fits. Main set vs held-out set in plain words.>

### <The levels>

<The levels, one line each.>

![<diagram alt text>](design/process-diagram.png)

## <4 · How it's scored, topic-specific heading>

<Each KPI in plain words, one short paragraph or bullet each.>

**What the article suggests:** <...>

**What I expect:** <the author's guesses, written before the runs>

## <5 · Results, topic-specific heading: main set first, then held-out>

<One line: the headline answer.>

### 1 · <Finding as a short sentence>

![<alt>](charts/<chart>.svg)

<2-4 sentences: what the graph shows, and why it matters.>

### What I expected vs. what happened

- <guess> → <what happened>

## <6 · Takeaways, topic-specific heading>

- **<takeaway>.** <one or two sentences>

## <7 · Limitations, topic-specific heading>

- **<limit>.** <one or two sentences>

**Data credit.** <dataset, authors, licence>. See [`data/NOTICE.md`](data/NOTICE.md).

## <8 · Technical walkthrough, topic-specific heading>

### <The data>

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
