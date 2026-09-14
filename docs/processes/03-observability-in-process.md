# Как локальная observability сидит в процессе

Каждый analyze создаёт `traces` + дерево `spans`.

- `LocalObservability.start_trace` пишет metadata: `application_id`, `model_version`, `prompt_version`, `rag_version`.
- Каждый узел графа — span с `code_path` и `mmd_node`.
- Retrieval пишет события `vector`, `bm25`, `rrf`, `rerank` — те же стадии, что на схеме hybrid RAG.
- `CreditLensCallback` ловит LangChain LLM/chain callbacks, если RouterAI включён.
- Фронт Observability Lab читает `GET /api/runs/{id}/trace` и подсвечивает узел mermaid.

LangSmith и Langfuse адаптеры существуют как `NotConfigured`. Runtime: `OBSERVABILITY=local`.

![Trace viewer](../screenshots/ui/observability-lab.png)
