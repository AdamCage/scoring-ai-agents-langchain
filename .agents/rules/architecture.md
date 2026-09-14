# Architecture

- One Docker image: FastAPI serves `frontend/dist`.
- Nginx terminates HTTP (TLS later). App and Langfuse bind in compose. Retrieval is in-memory, not Qdrant.
- LangGraph is a deterministic orchestrator plus specialized LangChain agents with tools.
- Shared state lives in `CreditState`. Reducers only append lists.
- Persistence: SQLite for checkpointer, traces, evals. Langfuse OSS for SaaS-like tracing.
- Keep provider-specific LLM code inside `creditlens/llm/routerai.py`.
