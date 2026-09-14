from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from contracts.application import Application
from contracts.evaluation import EvalResult, EvalRun

from creditlens.agents.runner import run_analysis
from creditlens.config import ROOT
from creditlens.db import get_conn
from creditlens.agents.risk_agent import REQUIRED_AGENT_TOOLS
from creditlens.evaluation.judge import judge_recommendation
from creditlens.evaluation.quality_gate import VARIANT_THRESHOLDS, evaluate_summary
from creditlens.evaluation.variants import PRODUCTION_VARIANT, get_variant, list_variants
from creditlens.llm.routerai import llm_available
from creditlens.observability.langfuse import public_url as langfuse_public_url
from creditlens.presets import presets
from creditlens.rag.retrieve import retrieve_policy
from creditlens.scoring.service import score_application

DATASETS = ROOT / "evals" / "datasets"
EXPERIMENTS = ROOT / "evals" / "experiments"


def _load_jsonl(name: str) -> list[dict]:
    path = DATASETS / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _scoring_cases() -> list[EvalResult]:
    results: list[EvalResult] = []
    for preset in presets():
        first = score_application(preset.application)
        second = score_application(preset.application)
        consistent = first == second
        results.append(
            EvalResult(
                case_id=preset.id,
                dataset="scoring_cases",
                metric="scoring_consistency",
                score=1.0 if consistent else 0.0,
                passed=consistent,
                comment="повторный вызов scoring tool",
                details=first.model_dump(),
            )
        )
        results.append(
            EvalResult(
                case_id=f"{preset.id}-structured",
                dataset="scoring_cases",
                metric="structured_output",
                score=1.0 if first.risk_band in {"LOW", "MEDIUM", "HIGH"} else 0.0,
                passed=first.risk_band in {"LOW", "MEDIUM", "HIGH"},
                details={"decision": first.decision},
            )
        )
    return results


def _rag_cases(mode: str, smoke: bool) -> list[EvalResult]:
    results: list[EvalResult] = []
    cases = _load_jsonl("rag_cases.jsonl") or [
        {
            "id": preset.id,
            "application": preset.application.model_dump(),
            "relevant": ["sme_credit_policy", "scoring_methodology", "manual_review"],
        }
        for preset in presets()
    ]
    if smoke:
        cases = cases[:6]
    for case in cases:
        app = Application.model_validate(case["application"])
        docs, _debug = retrieve_policy(app, extra_query=case.get("query", ""), mode=mode, top_k=5)
        retrieved = [doc.doc_id for doc in docs]
        relevant = set(case.get("relevant") or [])
        hit = len(relevant.intersection(retrieved))
        recall = hit / max(len(relevant), 1)
        mrr = 0.0
        for idx, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                mrr = 1.0 / (idx + 1)
                break
        precision = hit / max(len(retrieved), 1)
        results.append(
            EvalResult(
                case_id=case["id"],
                dataset="rag_cases",
                metric="recall_at_5",
                score=round(recall, 4),
                passed=recall >= 0.5,
                details={"retrieved": retrieved, "relevant": list(relevant), "mode": mode},
            )
        )
        results.append(
            EvalResult(
                case_id=f"{case['id']}-mrr",
                dataset="rag_cases",
                metric="mrr",
                score=round(mrr, 4),
                passed=mrr > 0,
                details={"retrieved": retrieved, "mode": mode},
            )
        )
        results.append(
            EvalResult(
                case_id=f"{case['id']}-citation",
                dataset="rag_cases",
                metric="citation_precision",
                score=round(precision, 4),
                passed=precision >= 0.25,
                details={"mode": mode},
            )
        )
    return results


def _agent_cases(smoke: bool, retrieval_mode: str, prompt_version: str) -> list[EvalResult]:
    results: list[EvalResult] = []
    items = presets()[:2] if smoke else presets()
    expected_prefix = ["validate_application", "calculate_score"]
    for preset in items:
        _run_id, state, _events = run_analysis(
            preset.application,
            hitl="auto",
            retrieval_mode=retrieval_mode,
            prompt_version=prompt_version,
        )
        trace = state.get("node_trace") or []
        has_score = "calculate_score" in trace
        prefix_ok = trace[:2] == expected_prefix or (
            "validate_application" in trace and "calculate_score" in trace
        )
        rec = state.get("recommendation")
        scoring = state.get("scoring")
        numeric_ok = bool(rec and scoring and rec.score == scoring.score and rec.decision == scoring.decision)
        citations = rec.citations if rec else []
        retrieved_docs = state.get("retrieved_documents") or []
        retrieved_citations = [doc.citation for doc in retrieved_docs]
        citation_ok = all(cite in retrieved_citations for cite in citations)
        tool_names = {
            item.get("name")
            for item in (state.get("tool_calls") or [])
            if isinstance(item, dict) and item.get("name")
        }
        agent_ok = set(REQUIRED_AGENT_TOOLS).issubset(tool_names)
        results.append(
            EvalResult(
                case_id=preset.id,
                dataset="agent_cases",
                metric="scoring_tool_called",
                score=1.0 if has_score else 0.0,
                passed=has_score,
                details={"node_trace": trace},
            )
        )
        results.append(
            EvalResult(
                case_id=f"{preset.id}-agent-tools",
                dataset="agent_cases",
                metric="agent_tool_usage",
                score=1.0 if agent_ok else 0.0,
                passed=agent_ok,
                comment="Risk Analyst called get_score_explanation + search_credit_policy",
                details={"tool_calls": sorted(tool_names)},
            )
        )
        results.append(
            EvalResult(
                case_id=f"{preset.id}-trajectory",
                dataset="agent_cases",
                metric="trajectory_superset",
                score=1.0 if prefix_ok and "synthesize" in trace else 0.0,
                passed=prefix_ok and "synthesize" in trace,
                details={"node_trace": trace},
            )
        )
        results.append(
            EvalResult(
                case_id=f"{preset.id}-numeric",
                dataset="agent_cases",
                metric="numeric_consistency",
                score=1.0 if numeric_ok else 0.0,
                passed=numeric_ok,
            )
        )
        results.append(
            EvalResult(
                case_id=f"{preset.id}-grounding",
                dataset="explanation_cases",
                metric="citation_grounding",
                score=1.0 if citation_ok else 0.0,
                passed=citation_ok,
                comment="citations ⊆ retrieved documents",
            )
        )
        if llm_available():
            judged = judge_recommendation(rec, scoring, state.get("shap"), retrieved_docs)
            if judged is not None:
                score, comment = judged
                results.append(
                    EvalResult(
                        case_id=f"{preset.id}-faithfulness",
                        dataset="explanation_cases",
                        metric="faithfulness",
                        score=score,
                        passed=score >= 0.9,
                        comment=comment,
                    )
                )
    return results


def run_evals(experiment: str = "hybrid-rerank", smoke: bool = False) -> EvalRun:
    variant = get_variant(experiment)
    started = datetime.now(UTC)
    run_id = str(uuid.uuid4())
    results = _scoring_cases()
    if not smoke:
        extra = _load_jsonl("scoring_cases.jsonl")
        for row in extra:
            app = Application.model_validate(row["application"])
            scored = score_application(app)
            ok = scored.decision == row.get("expected_decision", scored.decision)
            results.append(
                EvalResult(
                    case_id=row["id"],
                    dataset="scoring_cases",
                    metric="expected_decision",
                    score=1.0 if ok else 0.0,
                    passed=ok,
                    details=scored.model_dump(),
                )
            )
    results.extend(_rag_cases(mode=variant.retrieval, smoke=smoke))
    results.extend(
        _agent_cases(smoke=smoke, retrieval_mode=variant.retrieval, prompt_version=variant.prompt)
    )

    by_metric: dict[str, list[float]] = {}
    for item in results:
        by_metric.setdefault(item.metric, []).append(item.score)
    summary = {metric: round(sum(vals) / len(vals), 4) for metric, vals in by_metric.items()}
    ended = datetime.now(UTC)
    run = EvalRun(
        run_id=run_id,
        experiment=variant.name,
        started_at=started,
        ended_at=ended,
        status="ok",
        summary=summary,
        results=results,
        rag_version=f"{variant.retrieval}",
        prompt_version=variant.prompt,
        langfuse_url=langfuse_public_url(),
    )
    _persist(run)
    return run


def _persist(run: EvalRun) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO eval_runs(run_id, experiment, started_at, ended_at, status, summary_json, git_sha, rag_version, prompt_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run.run_id,
            run.experiment,
            run.started_at.isoformat(),
            run.ended_at.isoformat() if run.ended_at else None,
            run.status,
            json.dumps(run.summary),
            run.git_sha,
            run.rag_version,
            run.prompt_version,
        ),
    )
    for item in run.results:
        conn.execute(
            """
            INSERT INTO eval_results(run_id, case_id, dataset, metric, score, passed, comment, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                item.case_id,
                item.dataset,
                item.metric,
                item.score,
                int(item.passed),
                item.comment,
                json.dumps(item.details, ensure_ascii=False),
            ),
        )
    conn.commit()
    out = EXPERIMENTS / run.experiment
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")


def list_experiments() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT 20").fetchall()
    return [
        {
            "run_id": row["run_id"],
            "experiment": row["experiment"],
            "started_at": row["started_at"],
            "summary": json.loads(row["summary_json"]),
            "status": row["status"],
        }
        for row in rows
    ]


def latest_summary(experiment: str | None = None) -> dict:
    conn = get_conn()
    if experiment:
        row = conn.execute(
            "SELECT * FROM eval_runs WHERE experiment=? ORDER BY started_at DESC LIMIT 1",
            (experiment,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM eval_runs WHERE experiment=? ORDER BY started_at DESC LIMIT 1",
            (PRODUCTION_VARIANT,),
        ).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT 1").fetchone()
    if not row:
        return {}
    summary = json.loads(row["summary_json"])
    values = [value for value in summary.values() if isinstance(value, (int, float))]
    if values:
        summary["overall"] = round(sum(values) / len(values), 4)
    summary["experiment"] = row["experiment"]
    return summary


def latest_by_variant() -> dict[str, dict]:
    payload = {}
    for variant in list_variants():
        summary = latest_summary(variant.name)
        if not summary:
            continue
        thresholds = VARIANT_THRESHOLDS.get(variant.name)
        passed, failed = evaluate_summary(summary, thresholds, llm_enabled="faithfulness" in summary)
        payload[variant.name] = {
            "summary": summary,
            "gate": {"passed": passed, "failed": failed},
            "expected_gate": variant.expected_gate,
        }
    return payload
