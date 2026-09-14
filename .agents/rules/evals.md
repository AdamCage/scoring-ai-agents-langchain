# Evaluation

- Datasets live in `evals/datasets/*.jsonl` (≥30 cases total).
- Deterministic metrics must run without an LLM key.
- Quality gate (production / `hybrid-rerank`): scoring_consistency = 1, numeric_consistency = 1, citation_grounding ≥ 0.95, recall_at_5 ≥ 0.75, mrr ≥ 0.65. Missing required metric = FAIL.
- `faithfulness` ≥ 0.90 is required only for LLM-enabled full eval.
- `scoring_tool_called` = LangGraph ran `calculate_score`. `agent_tool_usage` = Risk Analyst called `get_score_explanation` and `search_credit_policy`.
- Experiments write SQLite + `evals/experiments/<name>/results.json`. The experiment name selects a real `EvalVariant`.
- Trajectory fail: recommendation without a scoring tool call.
