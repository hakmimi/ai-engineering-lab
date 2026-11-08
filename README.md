# ai-engineering-lab

Code for my blog posts at https://hakmimi.github.io/Blog/.

One folder per topic. Each one is based on an Anthropic article, rebuilt on a different use case.

```
topics/
  01-<topic>/
    README.md          what it is, takeaways, caveats, tradeoffs
    quick_setup/       the simple version
    better_version/    fixes for the caveats
    data/              sample inputs
    evals/             checks that show it works
    results.md         real numbers from my runs
shared/                code reused across topics (LLM client, cost/latency tracking)
```
