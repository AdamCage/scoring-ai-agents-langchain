Тогда я бы уже фиксировал один проект, а не выбирал дальше:

# **CreditLens — Agentic Credit Scoring & Explainability Lab**

Это интерактивная система для разбора кредитной заявки, где **классическая ML-модель принимает скоринговое решение, а LLM-агенты объясняют его, проверяют по кредитной политике через RAG и позволяют кредитному аналитику исследовать решение в диалоге**.

Ключевой смысл: не делать вид, что LLM заменяет scoring. Наоборот, показать зрелую архитектуру:

**ML отвечает за score → SHAP за локальную объяснимость → RAG за нормативное основание → агенты за анализ и диалог → evals контролируют качество всего контура.**

Это очень точно попадает и в вакансию, и в вопросы, которые тебе обозначили.

---

## 1. Пользовательский сценарий

Пользователь открывает публичный URL и видит несколько заранее подготовленных синтетических клиентов:

* низкий риск;
* пограничная заявка;
* высокий риск;
* хороший клиент с одним сильным негативным фактором;
* противоречивые данные;
* кейс, требующий ручного рассмотрения.

Можно либо выбрать готового клиента, либо заполнить форму самому.

Например:

```text
ООО «Альфа»
Выручка:             84 млн ₽
Возраст бизнеса:     6.2 года
Долговая нагрузка:   0.43
Просрочка 30+:       0
Запрос кредита:      12 млн ₽
Срок:                24 мес.
```

Нажимаем:

**«Проанализировать заявку»**

И начинается LangGraph workflow.

```text
Application
    ↓
Validation Agent
    ↓
Scoring Tool
    ↓
score = 0.73
    ├──────────────→ SHAP Explainer
    │
    └──────────────→ Policy RAG
                         ↓
                    Risk Analyst
                         ↓
                   Policy Critic
                         ↓
                   Final Synthesizer
                         ↓
                     Human Review
```

После этого пользователь получает не просто ответ:

> Рекомендуется одобрение.

А полноценную карточку:

```text
Рекомендация
ОДОБРЕНИЕ

Score           0.73
Risk band       Low
Confidence      High

Основные положительные факторы:
+ стабильная выручка
+ отсутствие просрочек
+ срок работы компании

Негативные факторы:
- повышенная долговая нагрузка

Основания:
[Кредитная политика → 4.2.3]
[Методика оценки МСБ → 7.1]
```

И дальше начинается самое интересное: **можно разговаривать с системой про конкретную заявку.**

Например:

> Почему заявка прошла при такой долговой нагрузке?

> Что больше всего повлияло на score?

> Какие правила кредитной политики применились?

> Что изменится, если сумма кредита станет 20 млн?

> Что нужно изменить клиенту, чтобы перейти в более низкий риск?

> Покажи только факторы, которые снизили score.

Это уже выглядит не как учебный LangChain tutorial, а как вполне нормальный банковский продукт.

---

# 2. Скоринг должен быть настоящим

Я бы не делал `score = random()` или rule-based заглушку.

Нужно сгенерировать небольшой **синтетический credit dataset** на 5–20 тысяч заявок и обучить настоящий `CatBoostClassifier`.

Features, например:

```text
company_age_months
annual_revenue
revenue_growth
ebitda_margin
debt_to_revenue
requested_amount
requested_term
credit_history_months
overdue_30d_count
overdue_90d_count
bureau_score
existing_loans_count
industry_risk
region_risk
```

Target — synthetic default.

В репозитории:

```text
models/
├── scoring_model.cbm
├── feature_schema.json
└── model_metadata.json
```

И отдельный deterministic tool:

```text
score_application(application) ->
{
    "pd": 0.073,
    "score": 0.73,
    "risk_band": "LOW",
    "decision": "APPROVE"
}
```

**LLM вообще не имеет права менять этот результат.**

Это важный архитектурный тезис для интервью.

---

# 3. Explainability через SHAP

Тут можно сделать одну из самых красивых частей интерфейса.

После scoring считаем SHAP для конкретного клиента.

Например:

```text
                    влияние на риск

debt_to_revenue       +0.14  █████████
industry_risk         +0.07  █████
requested_amount      +0.04  ███

company_age           -0.12  ████████
bureau_score          -0.18  ███████████
no_overdue            -0.21  █████████████
```

При этом есть два слоя explainability.

**Математический:**

> `bureau_score` снизил PD на X, а `debt_to_revenue` повысил его на Y.

И **LLM explanation:**

> Основным фактором в пользу клиента является качественная кредитная история. Повышенная долговая нагрузка увеличивает оценённый риск, однако её влияние компенсируют...

LLM получает только реальные SHAP values.

Это даёт нам ещё один прекрасный объект для evaluation:

> Не приписал ли LLM модели факторы, которых на самом деле нет?

---

# 4. RAG сделать серьёзнее обычного vector search

Я бы специально сделал **Hybrid RAG**, потому что именно этот термин есть в списке от Яндекса.

Создаём 10–20 небольших синтетических документов:

```text
knowledge_base/

credit_policy/
    general_policy.md
    sme_policy.md
    retail_policy.md

methodology/
    scoring_methodology.md
    risk_bands.md
    manual_review.md

regulations/
    borrower_requirements.md
    exceptions.md

products/
    sme_credit.md
    working_capital.md
```

Документы намеренно должны содержать:

* числа;
* лимиты;
* исключения;
* похожие формулировки;
* версии документа;
* segment metadata.

Например:

```yaml
document: sme_credit_policy
version: 3.2
effective_from: 2026-01-01
segment: sme
section: 4.2.3
```

Retrieval pipeline:

```text
Query
  │
  ├──── Vector retrieval
  │
  ├──── BM25 retrieval
  │
  └──── Metadata filters
             │
             ↓
             RRF
             ↓
          top 10
             ↓
          Reranker
             ↓
           top 4
             ↓
             LLM
```

Так на интервью ты сможешь не просто сказать «делал RAG», а открыть код и показать:

> «Здесь hybrid retrieval, здесь metadata filtering, здесь fusion, здесь reranking. А отдельно измеряется retrieval quality».

---

# 5. RouterAI

Здесь всё удобно: RouterAI сейчас предоставляет OpenAI-compatible API с base URL:

`https://routerai.ru/api/v1`

поэтому его нормально подключать через OpenAI/LangChain client с изменённым `base_url`. ([routerai.ru][1])

Модель я бы **не зашивал в код вообще**:

```env
ROUTERAI_API_KEY=
ROUTERAI_MODEL=
ROUTERAI_EMBEDDING_MODEL=openai/text-embedding-3-large
```

Embeddings через RouterAI тоже поддерживаются отдельным OpenAI-compatible `/embeddings` endpoint; `text-embedding-3-large` у них документирован. ([routerai.ru][2])

И обязательно единый adapter:

```text
src/llm/routerai.py
```

Чтобы LangGraph не знал ничего конкретного про провайдера.

---

# 6. LangGraph — не декоративный

Здесь есть хороший повод использовать state machine.

```python
class CreditState(TypedDict):
    application: Application
    validation: ValidationResult | None
    scoring: ScoringResult | None
    shap: ExplainabilityResult | None
    retrieved_documents: list[Document]
    analysis: RiskAnalysis | None
    critique: Critique | None
    recommendation: Recommendation | None
    messages: list
```

Граф:

```text
START
  ↓
validate_application

  ├── invalid → request_information
  │                  ↓
  │               INTERRUPT
  │                  ↓
  │            user provides data
  │                  ↓
  └──────────── validate_application
                     ↓
               calculate_score
                 ↙       ↘
          explain_score   retrieve_policy
                 ↘       ↙
                 risk_analysis
                      ↓
                policy_critic

          ┌───────────┴───────────┐
          ↓                       ↓
      insufficient             acceptable
          ↓                       ↓
   retrieve_more             synthesize
          └────────→──────────────┘
                                  ↓
                            human_review
                                  ↓
                                 END
```

Вот тут LangGraph уже действительно нужен:

* shared state;
* branches;
* cycles;
* tool calls;
* persistence;
* interrupt/resume;
* human-in-the-loop.

---

# 7. Frontend — одна из основных частей проекта

Я бы вообще не делал классический «чат на весь экран».

Нужен интерфейс **Credit Analyst Workbench**.

### Desktop

```text
┌─────────────────────────────────────────────────────────────┐
│ CreditLens     Applicant: ООО Альфа       RUN #A142         │
├───────────────┬───────────────────────────┬─────────────────┤
│               │                           │                 │
│ ЗАЯВКА        │ AGENT WORKSPACE           │ RISK            │
│               │                           │                 │
│ Выручка       │ ✓ Validation              │ Score 0.73      │
│ 84m           │ ✓ Scoring                 │ LOW RISK        │
│               │ ✓ SHAP                    │                 │
│ Сумма         │ ● Policy search           │ SHAP            │
│ 12m           │ ○ Risk analysis           │ █████ -0.21     │
│               │ ○ Critic                  │ ████  +0.14     │
│ ...           │                           │                 │
│               │ ─────────────────────     │ Sources         │
│ [ANALYZE]     │                           │ Policy §4.2     │
│               │ Chat...                   │ Method §7.1     │
└───────────────┴───────────────────────────┴─────────────────┘
```

Очень хорошо будет смотреться **live execution** графа:

```text
✓ Validation       87 ms
✓ Scoring          41 ms
✓ Explainability   73 ms
✓ Retrieval       243 ms
● Risk Analyst    1.4 s
○ Critic
○ Final
```

Это одновременно UX и observability.

---

# 8. Mobile надо проектировать отдельно

Не просто responsive shrinking.

На телефоне делаем нижнюю навигацию:

```text
┌───────────────────────┐
│ ООО Альфа             │
│ LOW RISK       0.73   │
├───────────────────────┤
│                       │
│ Agent conversation    │
│                       │
│ [Risk Analyst]        │
│ ...                   │
│                       │
├───────────────────────┤
│ Ask about decision... │
├───────────────────────┤
│ Заявка │ AI │ Risk │ KB│
└───────────────────────┘
```

4 вкладки:

**Заявка**

Форма клиента.

**AI**

Разговор с агентами + execution timeline.

**Risk**

Score + SHAP + what-if.

**Knowledge**

RAG sources и цитаты.

На desktop они становятся панелями одного workspace.

Для реализации я бы взял:

```text
React
TypeScript
Vite
Tailwind
shadcn/ui
Recharts
TanStack Query
```

Не Next.js: здесь он ничего принципиального не даёт, а deployment одного Python-контейнера становится проще.

---

# 9. Отдельно сделать What-if Analysis

Это может стать одной из лучших демонстраций.

После получения результата:

**What if?**

```text
Requested amount

12m ───────●────────────── 30m

Debt / revenue

0.43 ─────────●──────────── 0.80
```

Меняешь:

```text
requested_amount:
12m → 22m
```

и система мгновенно пересчитывает:

```text
Score
0.73 → 0.58

Risk
LOW → MEDIUM
```

SHAP перестраивается.

И можно спросить агента:

> Почему изменение суммы на 10 млн настолько сильно изменило решение?

А он сочетает:

**score + SHAP + RAG policy evidence.**

---

# 10. LangSmith

LangSmith использовать именно в нативном сценарии.

Каждая заявка:

```text
trace
└── langgraph.run
    ├── validate
    ├── scoring
    ├── shap
    ├── retrieval
    │   ├── vector
    │   ├── bm25
    │   └── rerank
    ├── risk_agent
    ├── critic
    └── synthesis
```

Metadata:

```json
{
  "application_id": "A142",
  "segment": "SME",
  "model_version": "catboost-v1",
  "prompt_version": "risk-v3",
  "rag_version": "hybrid-v2"
}
```

Это уже хороший разговор про production debugging.

---

# 11. Langfuse

Langfuse я бы тоже подключил.

Но не изображал бы, что нам в production обязательно нужны сразу оба продукта.

В README прямо:

> The project intentionally instruments the same agentic workflow with LangSmith and Langfuse to compare two observability approaches.

Это снимает вопрос «зачем два одинаковых сервиса?».

И можно сделать адаптеры:

```text
src/observability/

base.py
langsmith.py
langfuse.py
```

```env
OBSERVABILITY=both
```

---

# 12. LangSmith Evaluation — одна из главных фич

Заводим dataset:

```text
evals/datasets/
├── scoring_cases.jsonl
├── rag_cases.jsonl
├── explanation_cases.jsonl
└── agent_cases.jsonl
```

Не менее 30 кейсов.

### Deterministic evals

```text
scoring_consistency       = 100%
structured_output         = 100%
citation_validity         >= 98%
numeric_consistency       = 100%
required_tool_usage       = 100%
```

### RAG evals

```text
Recall@5
MRR
citation precision
context relevance
```

### LLM-as-a-Judge

```text
faithfulness
explanation quality
policy compliance
answer relevance
```

### Agent trajectory

Например:

```text
EXPECTED:

validate
→ scoring
→ retrieval
→ risk_analysis
→ critic
→ final
```

Failure:

```text
LLM immediately generates recommendation
without calling scoring tool

→ FAIL
```

---

# 13. Evaluation должна быть видна и во frontend

Я бы сделал отдельную страницу:

**Quality Lab**

```text
Quality overview

Overall                 94.3

Faithfulness            0.96
Policy compliance       0.98
RAG Recall@5            0.91
Citation precision      0.97
Decision consistency    1.00

Latency p50             1.4s
Latency p95             3.8s
```

И ниже:

```text
Experiments

baseline-rag      89.2
hybrid-rag        93.7   +4.5
hybrid-rerank     94.3   +0.6
```

Вот это уже очень сильно для интервью.

---

# 14. Агентская обвязка репозитория

Я бы сделал её такой:

```text
.
├── AGENTS.md
├── README.md
├── .env.example
│
├── .agents/
│   ├── rules/
│   │   ├── architecture.md
│   │   ├── security.md
│   │   ├── scoring.md
│   │   ├── rag.md
│   │   ├── evals.md
│   │   └── frontend.md
│   │
│   └── skills/
│       ├── scoring/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       ├── generate_dataset.py
│       │       └── train_model.py
│       │
│       ├── rag/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       ├── build_index.py
│       │       └── evaluate_retrieval.py
│       │
│       ├── langgraph/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       ├── validate_graph.py
│       │       └── export_graph.py
│       │
│       ├── evaluation/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       ├── run_evals.py
│       │       ├── analyze_failures.py
│       │       └── quality_gate.py
│       │
│       └── release/
│           ├── SKILL.md
│           └── scripts/
│               └── smoke_test.py
```

Это как раз выглядит «серьёзно», но ещё имеет реальное назначение.

---

# 15. Архитектура приложения

Я бы максимально упростил deployment:

```text
                         INTERNET
                            │
                            ▼
                 ┌─────────────────────┐
                 │    Docker App       │
                 │                     │
                 │ React static build  │
                 │        +            │
                 │     FastAPI         │
                 └──────────┬──────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
          RouterAI       LangSmith      Langfuse
              │
        ┌─────┴─────┐
        ▼           ▼
       LLM       Embeddings
```

То есть **один deployable Docker image**.

Frontend собирается Vite:

```text
frontend/dist/
```

и FastAPI раздаёт его как static files.

Это сильно проще, чем:

```text
Vercel
+
Render
+
CORS
+
2 deployments
+
2 domains
```

---

# 16. Про GitHub Actions есть важный нюанс

**GitHub Actions — CI/CD, а не хостинг backend.**

То есть правильная схема:

```text
git push
   ↓
GitHub Actions
   ├─ lint
   ├─ tests
   ├─ scoring tests
   ├─ RAG smoke eval
   ├─ frontend build
   ├─ Docker build
   ├─ quality gate
   └─ deploy
           ↓
       public host
```

Сам контейнер можно разместить на Render/Railway/Fly.io/VPS.

Для такого одноразового публичного demo я бы взял **Render или Railway**, а деплой запускал строго из GitHub Actions.

То есть требование выполняется:

> `git push main → GitHub Actions → production`.

---

# 17. CI/CD

Например:

```text
.github/workflows/

ci.yml
eval.yml
deploy.yml
```

### `ci.yml`

```text
ruff
mypy
pytest

npm lint
npm test
npm build
```

### `eval.yml`

```text
5-case smoke dataset
↓
LangSmith Evaluation
↓
quality_gate.py
```

Например:

```text
faithfulness < 0.90    → FAIL
citation_precision < .9 → FAIL
scoring_consistency < 1 → FAIL
```

### `deploy.yml`

```text
main
 ↓
test
 ↓
eval
 ↓
docker build
 ↓
deploy
 ↓
production smoke test
```

Это даст ещё одну отличную фразу на интервью:

> «У меня изменение prompt или retrieval pipeline не может попасть в demo production, если оно завалило минимальные eval thresholds».

---

# 18. Ключ RouterAI нельзя отдавать browser

Это принципиально.

Никаких:

```typescript
VITE_ROUTERAI_KEY=...
```

Ключ находится только:

```text
GitHub Actions Secrets
+
production backend environment
```

Frontend обращается:

```text
browser
  ↓
/api/agent
  ↓
FastAPI
  ↓
RouterAI
```

Учитывая, что demo будет доступно из интернета, я бы ещё сделал:

* rate limit;
* максимальное число agent steps;
* ограничение output tokens;
* timeout;
* доступ по простому demo password.

Иначе ссылку кто-нибудь найдёт и за ночь сожрёт баланс RouterAI.

---

# 19. Что должно быть готово к интервью

Не надо реализовывать банковскую АБС.

Достаточный вертикальный slice:

1. **5 красивых готовых клиентов.**
2. Настоящий `CatBoost`.
3. Настоящий SHAP.
4. 10–15 документов для RAG.
5. Hybrid retrieval.
6. LangGraph workflow.
7. Интерактивный chat.
8. What-if.
9. LangSmith traces.
10. Langfuse traces.
11. LangSmith Evaluation.
12. 20–30 eval cases.
13. Quality Lab.
14. Responsive UI.
15. GitHub Actions.
16. Public production deployment.

Вот это уже выглядит как **законченный LLM/ML engineering project**, а не домашняя работа перед собеседованием.

И я бы именно так сформулировал его цель в README:

> **CreditLens demonstrates how deterministic credit scoring, model explainability, RAG and agentic LLM workflows can be combined while keeping scoring decisions auditable, observable and continuously evaluated.**

Следующий шаг здесь уже не brainstorming. Стоит написать **one-shot ТЗ для coding-агента**, достаточно жёсткое, чтобы он сам развернул структуру репозитория, `AGENTS.md`, rules, skills, backend, frontend, evals, Docker и GitHub Actions, а после разработки прогнал acceptance criteria.

[1]: https://routerai.ru/docs/guides?utm_source=chatgpt.com "Обзор RouterAI — единый API к 100+ нейросетям | RouterAI"
[2]: https://routerai.ru/models/openai/text-embedding-3-large?utm_source=chatgpt.com "Text Embedding 3 Large — API в России, цены в рублях | RouterAI"

ок давай я тогда даже это на вм разверну в облаке?

Да. Для этого проекта **отдельная облачная VM даже лучше PaaS**: будет выглядеть как нормальный законченный сервис, а не временный demo на Render/Vercel. Плюс проще показать Docker, reverse proxy, healthchecks, CI/CD и observability.

Я бы зафиксировал такую архитектуру:

```text
                         Internet
                            │
                     https://creditlens...
                            │
                            ▼
                    ┌──────────────┐
                    │ Caddy/Nginx  │
                    │ TLS / HTTPS  │
                    └──────┬───────┘
                           │
                     Docker Compose
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
   ┌─────────────┐   ┌───────────┐    ┌───────────┐
   │ CreditLens  │   │  Qdrant   │    │ PostgreSQL│
   │             │   │           │    │ optional  │
   │ React       │   │ Vector DB │    │           │
   │ FastAPI     │   └───────────┘    └───────────┘
   │ LangGraph   │
   │ CatBoost    │
   │ SHAP        │
   │ BM25/RAG    │
   └──────┬──────┘
          │
          ├────────────→ RouterAI
          │
          ├────────────→ LangSmith
          │
          └────────────→ Langfuse Cloud
```

### VM я бы взял примерно такую

Для demo более чем достаточно:

```text
4 vCPU
8 GB RAM
80–100 GB SSD
Ubuntu 24.04
Public IPv4
```

Даже `2 vCPU / 4 GB` скорее всего заведётся, но **4/8** лучше: CatBoost + SHAP + Python + Qdrant + сборка/перезапуск контейнеров без неприятных пауз.

GPU здесь вообще не нужен — LLM идут через RouterAI.

### Не надо тащить на эту VM всё подряд

Я бы специально **не self-host'ил LangSmith и Langfuse** ради демонстрации.

Используем:

* **LangSmith SaaS**;
* **Langfuse Cloud**;
* **RouterAI**;
* локально на VM — только само приложение и Qdrant.

Иначе вместо изучения evals ты сегодня будешь чинить ClickHouse/Postgres/Redis для Langfuse.

PostgreSQL тоже сначала можно вообще не ставить. Для состояния LangGraph и демонстрационных кейсов достаточно SQLite или файлового storage. Если агент быстро всё реализует — потом перевести checkpointer на Postgres.

---

## Deployment

Получится нормальный production-like процесс:

```text
Developer
   │
   │ git push
   ▼
GitHub
   │
   ▼
GitHub Actions
   │
   ├── backend tests
   ├── frontend tests
   ├── lint
   ├── build
   ├── eval smoke tests
   └── docker build
           │
           ▼
       GHCR image
           │
           ▼
          SSH
           │
           ▼
      Cloud VM
           │
      docker compose pull
      docker compose up -d
           │
           ▼
       smoke test
```

То есть image хранится в **GitHub Container Registry**:

```text
ghcr.io/<username>/creditlens:<sha>
ghcr.io/<username>/creditlens:latest
```

VM ничего не собирает.

Это правильнее, чем `git pull && docker compose build` непосредственно на сервере.

---

## Docker Compose

Примерно:

```yaml
services:
  app:
    image: ghcr.io/USER/creditlens:latest
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - qdrant
    ports:
      - "127.0.0.1:8000:8000"

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"

  caddy:
    image: caddy:latest
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config

volumes:
  qdrant_data:
  caddy_data:
  caddy_config:
```

И я бы взял именно **Caddy**, а не nginx: для demo HTTPS получишь практически бесплатно.

```text
creditlens.example.ru {
    reverse_proxy app:8000
}
```

Caddy сам получает и обновляет Let's Encrypt certificate.

---

## Frontend тоже не надо отдельно хостить

Проще:

```text
React
   ↓ npm run build
frontend/dist
   ↓
копируется в Python Docker image
   ↓
FastAPI StaticFiles
```

И тогда наружу у нас одна система:

```text
GET /
GET /assets/...
POST /api/applications
POST /api/analyze
POST /api/chat
POST /api/what-if
GET /api/runs/{id}
GET /api/health
```

Никакого CORS и двух разных deployment pipelines.

---

## Secrets

На VM:

```env
ROUTERAI_API_KEY=...
ROUTERAI_MODEL=...

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=creditlens

LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=...

DEMO_PASSWORD=...
```

В GitHub:

```text
VM_HOST
VM_USER
VM_SSH_KEY

GHCR credentials
```

Сам `ROUTERAI_API_KEY` я бы **вообще не передавал через GitHub Actions**, если нет необходимости.

Один раз кладём `.env` непосредственно на сервер:

```text
/opt/creditlens/.env
```

и CI его не трогает.

Так меньше шансов случайно засветить ключ.

---

# Я бы ещё сделал Basic Auth / Demo login

Поскольку URL публичный и RouterAI платный, просто выпускать наружу `/api/chat` нельзя.

Самый красивый вариант — стартовый экран:

```text
┌──────────────────────────┐
│                          │
│        CreditLens        │
│                          │
│ Agentic Credit           │
│ Intelligence Platform    │
│                          │
│ Demo access              │
│ [ ••••••••••••• ]       │
│                          │
│       Enter demo         │
│                          │
└──────────────────────────┘
```

Плюс backend rate limiting:

```text
10 agent runs / minute / IP
30 chat messages / hour / IP
```

И hard limits:

```text
max_agent_steps = 12
max_output_tokens = ...
timeout = 60 sec
```

Это важно именно для публичного deployment.

---

# Ещё один хороший эффект VM

Мы можем добавить в интерфейс:

**System status**

```text
System Status

● API                 healthy
● Scoring model       catboost-v1
● Vector index        ready
● Knowledge base      18 documents
● LLM provider        RouterAI
● LangSmith           enabled
● Langfuse            enabled

Build
9e8a41c

Environment
production
```

И commit SHA прокидывать из GitHub Actions:

```text
APP_VERSION=${GITHUB_SHA}
```

Мелочь, но на техническом интервью выглядит хорошо.

---

# Что я бы выбрал для облака

Для самого проекта провайдер вообще не принципиален. Подойдёт:

* Yandex Cloud;
* Selectel;
* Timeweb Cloud;
* любой обычный VPS/VDS.

Если хочется дополнительного символизма перед собеседованием в Яндекс — можно развернуть в **Yandex Cloud**, но технической необходимости в этом нет.

Главное — получить:

```text
Ubuntu VM
4 vCPU
8 GB
public IPv4
SSH
DNS A-record
```

---

## В итоге

Я бы теперь принял как фиксированные требования:

```text
CreditLens

Cloud VM
├── Ubuntu 24.04
├── Docker Compose
├── Caddy + HTTPS
├── FastAPI
├── React / TypeScript / Tailwind / shadcn
├── LangGraph
├── LangChain
├── CatBoost
├── SHAP
├── Hybrid RAG
│   ├── Qdrant
│   ├── BM25
│   └── reranker
├── RouterAI
├── LangSmith
│   ├── tracing
│   ├── datasets
│   └── evaluation
└── Langfuse
    └── observability

GitHub Actions
├── CI
├── tests
├── eval quality gate
├── Docker → GHCR
└── SSH deploy → VM
```

Это уже хорошая исходная архитектура для **one-shot ТЗ агенту**. Причём в ТЗ я бы сразу дал ему обязанность не только написать проект, но и самостоятельно создавать/поддерживать `AGENTS.md`, rules, skills со скриптами, архитектурную документацию, eval dataset, CI/CD и deployment-инструкцию.
