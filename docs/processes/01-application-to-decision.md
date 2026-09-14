# От заявки до решения

Пользователь выбирает один из шести синтетических клиентов или заполняет форму. FastAPI принимает `POST /api/analyze` и запускает LangGraph.

```mermaid
flowchart LR
  Form[Заявка] --> Validate[Validation]
  Validate --> Score[CatBoost]
  Score --> SHAP[SHAP]
  Score --> RAG[HybridRAG]
  SHAP --> Risk[RiskAnalyst]
  RAG --> Risk --> Critic[PolicyCritic] --> Card[Карточка]
```

Карточка всегда берёт `decision`, `score` и `risk_band` из `ScoringResult`. LLM пишет только текст.

![Workbench](../screenshots/ui/workbench-desktop.png)
