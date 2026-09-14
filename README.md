# CreditLens

**Agentic Credit Scoring & LLM Evaluation Lab.** Deterministic ML scoring, explainability and banking policy RAG orchestrated with LangGraph. Every agent run is traced, evaluated and regression-tested before deployment.

ML считает score. SHAP объясняет. Hybrid RAG цитирует политику. LangGraph оркестрирует workflow и HITL. LangChain-агенты вызывают tools. LLM **не имеет права** переписать `ScoringResult`.

## Что внутри

- CatBoost + SHAP на синтетическом credit dataset
- Hybrid RAG: metadata filter → vector + BM25 → RRF → local rerank (in-memory index)
- LangGraph: validation, scoring, параллельные SHAP/RAG, Risk Analyst, LLM Critic, synthesis, human interrupt
- LangChain `create_agent` только в Risk Analyst: read-only tools + structured output. Critic — structured Critique + guard
- Observability: локальные SQLite spans + self-hosted Langfuse OSS (traces/datasets). LangSmith — native Evaluation (`Client.evaluate()`), включается ключом
- Experiment Lab: настоящие pipeline variants (`vector-only`, `hybrid`, `hybrid-rerank`, `bad-prompt`) и quality gate
- Один Docker-образ: FastAPI раздаёт `frontend/dist`
- nginx на VM: IP `:8080`, домен `https://credit-adamcage.ru`

## Быстрый старт

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
python scripts/train_model.py
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=.:backend/src uvicorn creditlens.main:app --app-dir backend/src --reload --port 8000
```

Авторизации нет — демо открывается сразу.

Откройте `http://127.0.0.1:8000` — Workbench, Architecture, Observability, Experiment Lab.

Langfuse OSS:

```bash
docker compose up -d langfuse langfuse-db
```

UI: `http://127.0.0.1:3000` (demo@creditlens.local / creditlens-demo).

## Документация процессов

- [От заявки до решения](docs/processes/01-application-to-decision.md)
- [LangChain в процессе](docs/processes/02-langchain-in-process.md)
- [Observability](docs/processes/03-observability-in-process.md)
- [Evaluation](docs/processes/04-evaluation-in-process.md)
- [Hybrid RAG](docs/processes/05-hybrid-rag.md)
- [What-if и чат](docs/processes/06-what-if-and-chat.md)
- [Деплой nginx/VM](docs/processes/07-deploy-nginx-vm.md)

Агентам: см. [AGENTS.md](AGENTS.md).
