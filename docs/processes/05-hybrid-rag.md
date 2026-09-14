# Hybrid RAG

Документы в `knowledge_base/` имеют YAML: `document`, `version`, `effective_from`, `segment`, `section`.

Пайплайн: metadata filter по сегменту → vector + BM25 → RRF → локальный rerank → top 4.

Без RouterAI embeddings считаются детерминированным hash-вектором, чтобы тесты и CI были воспроизводимы. При наличии ключа используется OpenAI-compatible `/embeddings` с `check_embedding_ctx_length=False`.

![Hybrid RAG](../screenshots/diagrams/hybrid-rag.png)
