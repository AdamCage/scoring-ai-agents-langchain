# Release skill

```bash
python scripts/smoke_test.py
python -m creditlens.evaluation.run_evals --experiment hybrid-rerank --smoke
python -m creditlens.evaluation.quality_gate --experiment hybrid-rerank
docker compose -f deploy/compose/docker-compose.yml up -d
```

CI on `main` is `test → eval(hybrid-rerank) → deploy`. Deploy must not start if the quality gate fails.
Langfuse is part of compose. Qdrant is not in the runtime path.
