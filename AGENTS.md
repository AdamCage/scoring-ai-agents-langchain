# CreditLens agent guide

CreditLens is an agentic credit workbench: **CatBoost scores, SHAP explains, hybrid RAG cites policy, LangGraph agents analyze, local evals gate quality**. The LLM never overwrites `ScoringResult`.

## Ownership

Change only the directories you own. Shared contracts are frozen after Wave 0.

- `contracts/` and generated OpenAPI — foundation only
- `backend/src/creditlens/scoring/` — scoring agent
- `backend/src/creditlens/rag/` + `knowledge_base/` — rag agent
- `backend/src/creditlens/agents/` — graph agent
- `backend/src/creditlens/observability/` — obs agent
- `backend/src/creditlens/evaluation/` + `evals/` — eval agent
- `frontend/` — frontend agent (import API types, do not fork pydantic models)
- `docs/` + `scripts/capture_docs.py` — docs agent
- `deploy/` + `.github/workflows/` — release agent

## Invariants

1. `ScoringResult` is written only by the scoring tool.
2. RouterAI keys stay on the backend. No `VITE_*` LLM secrets.
3. Observability default is dual-write: local SQLite + Langfuse OSS when configured. LangSmith is the same adapter and stays `ready_no_key` until `LANGSMITH_API_KEY` is set. Do not claim the adapters are intentionally disabled.
4. Docs in `docs/architecture/*.mmd` and `docs/processes/*.md` are the source of truth for Architecture Explorer.
5. UI copy and process docs are Russian. Code identifiers are English.
6. A new LLM node needs a Pydantic schema, eval cases and trace metadata.

## Local commands

```bash
python -m pip install -e ".[dev]"
python scripts/train_model.py
python -m creditlens.rag.build_index
pytest
cd frontend && npm install && npm run build
uvicorn creditlens.main:app --app-dir backend/src --reload --port 8000
```

See `.agents/rules/` and `.agents/skills/` for domain rules and scripts.
