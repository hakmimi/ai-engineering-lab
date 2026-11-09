# Data notice

The sessions in this folder come from **AgentDojo**:

> Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr.
> *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.* NeurIPS 2024 Datasets and Benchmarks.
> https://github.com/ethz-spylab/agentdojo

- Source: the saved agent runs in `runs/gpt-4o-2024-05-13/`, at commit `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
- Licence: MIT (below). The raw run files are not copied here; `agentreview/build_data.py` rebuilds these files from a local clone.

## What was changed

- Each run's chat was turned into numbered events (`agentreview/transcript.py`).
- Removed from what the reviewer sees: `injections`, `security`, `utility`, `attack_type`, `injection_task_id`,
  `user_task_id`, `pipeline_name`, `duration`, `error`, and the tool-call ids. Sessions got new ids (`m-`, `t-`, `f-`).
- The answer (`bad` = the attack worked, `refused` = the attack was there but did not work, `clean` = no attack),
  the source path and the attack style are kept in `key.json`, which the review code never reads.
- `fooled.json`: the test set's bad sessions with one added paragraph after the planted text (the exact wording is in the file's `note` field).
- `grants.json` is ours, written for this topic.

## AgentDojo licence

MIT License

Copyright (c) 2024 Edoardo Debenedetti, Jie Zhang, Mislav Balunovic, Luca Beurer-Kellner, Marc Fischer, and Florian Tramèr

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
