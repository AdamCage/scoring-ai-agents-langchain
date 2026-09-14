# Architecture

- One Docker image: FastAPI serves `frontend/dist`.
- Nginx terminates HTTP (TLS later). App and Qdrant bind to localhost in compose.
- LangGraph is a deterministic orchestrator plus specialized agents with tools.
- Shared state lives in `CreditState`. Reducers only append lists.
- Persistence: SQLite for checkpointer, traces, evals.
- Keep provider-specific LLM code inside `creditlens/llm/routerai.py`.
