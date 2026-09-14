# Как evaluation закрывает контур

Датасеты: `evals/datasets/{scoring,rag,explanation,agent}_cases.jsonl` (≥30 кейсов вместе с пресетами).

Слои:

- детерминированные: `scoring_consistency`, `structured_output`, `numeric_consistency`, `required_tool_usage`
- RAG: Recall@5, MRR, citation precision
- trajectory: validate → score → retrieve → risk → critic → synthesize
- faithfulness: цитаты ⊆ retrieved documents

Раннер пишет SQLite и `evals/experiments/<name>/results.json`. CI вызывает `quality_gate.py`.

Quality Lab показывает overview и сравнение `baseline-rag` / `hybrid-rag` / `hybrid-rerank`.

![Quality Lab](../screenshots/ui/quality-lab.png)
