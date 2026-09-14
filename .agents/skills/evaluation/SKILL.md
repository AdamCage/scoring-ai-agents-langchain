# Evaluation skill

Variants are real pipelines, not labels:

- `vector-only` — naive vector retrieval, expected FAIL
- `hybrid` — vector + BM25 + RRF
- `hybrid-rerank` — production path, deploy gate
- `bad-prompt` — injects an ungrounded citation, expected FAIL

```bash
python -m creditlens.evaluation.run_evals --experiment hybrid-rerank --smoke
python -m creditlens.evaluation.quality_gate --experiment hybrid-rerank
python -m creditlens.evaluation.sync_dataset
python -m creditlens.evaluation.run_langfuse_eval
python -m creditlens.evaluation.run_langsmith_eval
python -m creditlens.evaluation.compare_experiments
```

`citation_grounding` is the deterministic “citations ⊆ retrieved docs” check.
`faithfulness` is LLM-as-a-Judge over ScoringResult + SHAP features + retrieved text.
`scoring_tool_called` checks LangGraph ran `calculate_score`.
`agent_tool_usage` requires Risk Analyst tools `get_score_explanation` and `search_credit_policy`.
Missing required production metrics fail the gate. `faithfulness` is required only in LLM-enabled full eval.

Expected gate: `vector-only` FAIL, `hybrid` PASS, `hybrid-rerank` PASS, `bad-prompt` FAIL grounding.

LangSmith Evaluation is `Client.evaluate()` on dataset `creditlens-smoke`, experiment `creditlens-hybrid-rerank-v1`. Without `LANGSMITH_API_KEY` the script stays `ready_no_key`.
Deploy quality gate reads only `hybrid-rerank`.
