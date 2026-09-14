# Evaluation

- Datasets live in `evals/datasets/*.jsonl` (≥30 cases total).
- Deterministic metrics must run without an LLM key.
- Quality gate: scoring_consistency = 1, citation_precision ≥ 0.9, faithfulness ≥ 0.90 when judge is available.
- Experiments write SQLite + `evals/experiments/<name>/results.json`.
- Trajectory fail: recommendation without a scoring tool call.
