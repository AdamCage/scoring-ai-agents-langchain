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
python -m creditlens.evaluation.compare_experiments
```

`citation_grounding` is the deterministic “citations ⊆ retrieved docs” check.
`faithfulness` is LLM-as-a-Judge and is skipped without `LLM_API_KEY`.
Deploy quality gate reads only `hybrid-rerank`.
