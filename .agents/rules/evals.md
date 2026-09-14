# Evaluation

- Datasets live in `evals/datasets/*.jsonl` (≥30 cases total).
- Deterministic metrics must run without an LLM key.
- Quality gate (production / `hybrid-rerank`): scoring_consistency = 1, citation_precision ≥ 0.25, citation_grounding ≥ 0.7, required_tool_usage = 1, numeric_consistency = 1.
- `faithfulness` is LLM-as-a-Judge and is omitted from the gate when no key is present.
- Experiments write SQLite + `evals/experiments/<name>/results.json`. The experiment name selects a real `EvalVariant`.
- Trajectory fail: recommendation without a scoring tool call.
