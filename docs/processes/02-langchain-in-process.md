# Как LangChain / LangGraph участвуют в процессе

Технический путь:

1. `creditlens.llm.routerai.chat_model()` создаёт `ChatOpenAI` с `base_url=https://routerai.ru/api/v1`. Граф не знает провайдера.
2. `StateGraph(CreditState)` оркестрирует узлы, checkpointer и HITL. Score пишет только `calculate_score`.
3. Параллельные рёбра: после scoring идут `explain_score` и `retrieve_policy`, затем join в `risk_analysis`.
4. `risk_analysis` и `policy_critic` — LangChain agent nodes: tools / structured output. Нет ключа — детерминированный fallback.
5. `policy_critic` может вернуть выполнение в `retrieve_more` (цикл).
6. `human_review` вызывает `interrupt()`. Resume того же `thread_id` через `Command(resume=...)`.
7. Стрим: события `node_start` уходят в SSE в момент входа в node, не после `graph.stream` update.

Код-пути, которые показывает Architecture Explorer:

- `creditlens.agents.graph.build_graph`
- `creditlens.agents.risk_agent.run_risk_analyst`
- `creditlens.scoring.service.score_application`
- `creditlens.rag.retrieve.retrieve_policy`
- `creditlens.llm.routerai.chat_model`

![LangChain runtime](../screenshots/ui/architecture-langchain.webp)
