# Observability skill

CreditLens dual-writes every LangGraph run:

- local SQLite for the in-app Observability Lab
- Langfuse OSS when `LANGFUSE_HOST` + project keys are set
- LangSmith when `LANGSMITH_API_KEY` is set (same protocol, optional SaaS sink)

```bash
python -m creditlens.observability.inspect_trace --limit 5
python -m creditlens.observability.inspect_trace --run-id <run_id>
```

Rules for a new LLM node:

1. Structured Pydantic schema for the node output.
2. At least one eval case in `evals/datasets/`.
3. Trace metadata: `application_id`, `model_version`, `prompt_version`, `rag_version`.
4. Do not claim LangSmith is disabled. Say `ready_no_key` or `enabled`.
