# CreditLens

**CreditLens demonstrates how deterministic credit scoring, model explainability, RAG and agentic LLM workflows can be combined while keeping scoring decisions auditable, observable and continuously evaluated.**

ML считает score. SHAP объясняет. Hybrid RAG цитирует политику. LangGraph-агенты анализируют. Локальные evals не пускают регресс. LLM **не имеет права** переписать `ScoringResult`.

## Что внутри

- CatBoost + SHAP на синтетическом credit dataset
- Hybrid RAG: metadata filter → vector + BM25 → RRF → local rerank
- LangGraph: validation, scoring, SHAP, retrieval, risk analyst, policy critic, synthesizer, human review
- Локальная observability (SQLite traces). LangSmith/Langfuse — `NotConfigured`
- Quality Lab и Architecture Explorer (те же `.mmd` / `.md`, что в `docs/`)
- Один Docker-образ: FastAPI раздаёт `frontend/dist`
- nginx на VM: IP `:8080`, домен `https://credit-adamcage.ru` (Let's Encrypt, отдельный server_name)

## Быстрый старт

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
python scripts/train_model.py
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=.:backend/src uvicorn creditlens.main:app --app-dir backend/src --reload --port 8000
```

Demo-пароль по умолчанию: `creditlens-demo`.

Откройте `http://127.0.0.1:8000` или `https://credit-adamcage.ru` — Workbench, Architecture, Observability, Quality Lab.

## Документация процессов

- [От заявки до решения](docs/processes/01-application-to-decision.md)
- [LangChain в процессе](docs/processes/02-langchain-in-process.md)
- [Observability](docs/processes/03-observability-in-process.md)
- [Evaluation](docs/processes/04-evaluation-in-process.md)
- [Hybrid RAG](docs/processes/05-hybrid-rag.md)
- [What-if и чат](docs/processes/06-what-if-and-chat.md)
- [Деплой nginx/VM](docs/processes/07-deploy-nginx-vm.md)

Агентам: см. [AGENTS.md](AGENTS.md).
