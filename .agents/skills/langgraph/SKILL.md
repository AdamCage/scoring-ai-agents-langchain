# LangGraph skill

LangGraph owns the stateful workflow: branching, parallel SHAP/RAG, critic retry, HITL.
LangChain `create_agent` owns tool use and structured output inside the Risk Analyst node.
The Policy / LLM Critic is `with_structured_output(Critique)` plus a deterministic guard — not an agent.

```bash
python -m creditlens.agents.validate_graph
python -m creditlens.agents.export_graph
python -m creditlens.agents.smoke_interrupt_resume
```

HITL: `SqliteSaver` checkpointer + `interrupt()` in `human_review`.
Resume the same `thread_id` with `Command(resume=...)` via `POST /api/runs/{id}/resume`.

A new LLM node must ship a Pydantic schema, eval cases, and trace metadata.
Do not let the LLM write `ScoringResult`.
