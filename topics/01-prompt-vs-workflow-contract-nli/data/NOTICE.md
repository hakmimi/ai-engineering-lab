# Data notice

The contracts and labels in `main.json` and `test.json` come from **ContractNLI**:

> Yuta Koreeda and Christopher D. Manning. 2021. ContractNLI: A Dataset for Document-level Natural Language
> Inference for Contracts. Findings of the Association for Computational Linguistics: EMNLP 2021.
> https://stanfordnlp.github.io/contract-nli/

ContractNLI is released by Hitachi America, Ltd. under the Creative Commons Attribution 4.0 International
licence (CC BY 4.0, https://creativecommons.org/licenses/by/4.0/).

What was changed: 60 of the 607 NDAs were drawn at random (seed 2026): 30 from the dev split (`main.json`)
and 30 from the test split (`test.json`). Each NDA is stored as its list of spans (the dataset's own
sentence/list-item split, whitespace trimmed); the contract text itself is unchanged. Labels were renamed
(Entailment → entailment, Contradiction → contradiction, NotMentioned → not_mentioned). The 17 statements in
`statements.json` are the dataset's hypotheses, unchanged.
