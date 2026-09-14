from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.application import Application
from creditlens.agents.runner import run_analysis
from creditlens.config import ROOT
from creditlens.evaluation.judge import judge_faithfulness
from creditlens.llm.routerai import llm_available
from creditlens.observability.langsmith import available, configure_env
from creditlens.presets import presets

DATASET_NAME = "creditlens-smoke"
EXPERIMENT_NAME = "creditlens-hybrid-rerank-v1"
REQUIRED_TOOLS = {"get_score_explanation", "search_credit_policy"}
STATE_PATH = ROOT / "evals" / "experiments" / "langsmith.json"


def _examples() -> list[dict[str, Any]]:
    rows = []
    for preset in presets()[:2]:
        rows.append(
            {
                "inputs": {
                    "id": preset.id,
                    "application": preset.application.model_dump(),
                },
                "outputs": {"expected_decision": None},
            }
        )
    return rows


def _analyze(inputs: dict[str, Any]) -> dict[str, Any]:
    app = Application.model_validate(inputs["application"])
    _run_id, state, _events = run_analysis(
        app,
        hitl="auto",
        retrieval_mode="hybrid-rerank",
        prompt_version="risk-v1",
    )
    rec = state.get("recommendation")
    scoring = state.get("scoring")
    shap = state.get("shap")
    docs = state.get("retrieved_documents") or []
    tools = [item.get("name") for item in (state.get("tool_calls") or []) if isinstance(item, dict)]
    return {
        "decision": rec.decision if rec else None,
        "score": rec.score if rec else None,
        "summary": rec.summary if rec else "",
        "citations": rec.citations if rec else [],
        "scoring_decision": scoring.decision if scoring else None,
        "scoring_score": scoring.score if scoring else None,
        "scoring": scoring.model_dump() if scoring else None,
        "shap": shap.model_dump() if shap else None,
        "node_trace": state.get("node_trace") or [],
        "retrieved_citations": [doc.citation for doc in docs],
        "documents": [doc.model_dump() for doc in docs],
        "tool_calls": tools,
    }


def _numeric(outputs: dict[str, Any]) -> dict[str, Any]:
    ok = outputs.get("score") == outputs.get("scoring_score") and outputs.get("decision") == outputs.get(
        "scoring_decision"
    )
    return {"key": "numeric_consistency", "score": 1.0 if ok else 0.0}


def _grounding(outputs: dict[str, Any]) -> dict[str, Any]:
    retrieved = set(outputs.get("retrieved_citations") or [])
    citations = outputs.get("citations") or []
    ok = all(cite in retrieved for cite in citations)
    return {"key": "citation_grounding", "score": 1.0 if ok else 0.0}


def _trajectory(outputs: dict[str, Any]) -> dict[str, Any]:
    trace = outputs.get("node_trace") or []
    ok = "validate_application" in trace and "calculate_score" in trace and "synthesize" in trace
    return {"key": "trajectory", "score": 1.0 if ok else 0.0}


def _faithfulness(outputs: dict[str, Any]) -> dict[str, Any]:
    from contracts.rag import RetrievedDocument
    from contracts.scoring import ScoringResult, ShapResult

    if not llm_available():
        return {"key": "llm_faithfulness", "score": 0.0, "comment": "skipped: no LLM key"}
    scoring = ScoringResult.model_validate(outputs["scoring"]) if outputs.get("scoring") else None
    shap = ShapResult.model_validate(outputs["shap"]) if outputs.get("shap") else None
    docs = [RetrievedDocument.model_validate(item) for item in outputs.get("documents") or []]
    score, comment = judge_faithfulness(str(outputs.get("summary") or ""), scoring, shap, docs)
    return {"key": "llm_faithfulness", "score": score, "comment": comment}


def _wrap_evaluator(fn):
    def evaluator(run: Any, example: Any) -> dict[str, Any]:
        outputs = getattr(run, "outputs", None) or {}
        return fn(outputs)

    evaluator.__name__ = getattr(fn, "__name__", "evaluator")
    return evaluator


def _save(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_experiment() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"status": "ready_no_key" if not available() else "missing", "url": None}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def run_langsmith_eval(*, upload: bool = True) -> dict[str, Any]:
    examples = _examples()
    local_rows = []
    for example in examples:
        outputs = _analyze(example["inputs"])
        scores = [_numeric(outputs), _grounding(outputs), _trajectory(outputs), _faithfulness(outputs)]
        local_rows.append({"id": example["inputs"]["id"], "outputs": outputs, "scores": scores})

    payload: dict[str, Any] = {
        "dataset": DATASET_NAME,
        "experiment": EXPERIMENT_NAME,
        "status": "local_only",
        "url": None,
        "results": [
            {"id": row["id"], "scores": {item["key"]: item["score"] for item in row["scores"]}} for row in local_rows
        ],
    }
    if not available() or not upload:
        payload["status"] = "ready_no_key"
        _save(payload)
        return payload

    configure_env()
    try:
        from langsmith import Client
        from langsmith.evaluation import evaluate

        client = Client()
        try:
            client.read_dataset(dataset_name=DATASET_NAME)
        except Exception:
            client.create_dataset(
                dataset_name=DATASET_NAME,
                description="CreditLens smoke applications for LangSmith Evaluation",
            )
        existing = {getattr(item, "inputs", {}).get("id") for item in client.list_examples(dataset_name=DATASET_NAME)}
        for example in examples:
            if example["inputs"]["id"] in existing:
                continue
            client.create_example(
                dataset_name=DATASET_NAME,
                inputs=example["inputs"],
                outputs=example.get("outputs") or {},
            )
        result = evaluate(
            _analyze,
            data=DATASET_NAME,
            evaluators=[
                _wrap_evaluator(_numeric),
                _wrap_evaluator(_grounding),
                _wrap_evaluator(_trajectory),
                _wrap_evaluator(_faithfulness),
            ],
            experiment_prefix=EXPERIMENT_NAME,
            max_concurrency=1,
        )
        url = getattr(result, "experiment_url", None) or getattr(result, "url", None)
        if url is None:
            project = client.read_project(project_name=EXPERIMENT_NAME)
            url = getattr(project, "url", None)
        payload["status"] = "uploaded"
        payload["url"] = url
    except Exception as exc:
        payload["status"] = "error"
        payload["error"] = str(exc)
    _save(payload)
    return payload


def main() -> None:
    result = run_langsmith_eval()
    print(result["experiment"], result["status"], result.get("url") or "no-url")
    for row in result.get("results") or []:
        print(row["id"], row["scores"])


if __name__ == "__main__":
    main()
