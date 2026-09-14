from __future__ import annotations

import json
import sys

from creditlens.config import ROOT
from creditlens.llm.routerai import llm_available

PRODUCTION_REQUIRED = {
    "scoring_consistency": 1.0,
    "numeric_consistency": 1.0,
    "citation_grounding": 0.95,
    "recall_at_5": 0.75,
    "mrr": 0.65,
}

LLM_REQUIRED = {
    "faithfulness": 0.90,
}

THRESHOLDS = {**PRODUCTION_REQUIRED}

VARIANT_THRESHOLDS = {
    "vector-only": {**PRODUCTION_REQUIRED},
    "hybrid": {**PRODUCTION_REQUIRED},
    "hybrid-rerank": {**PRODUCTION_REQUIRED},
    "bad-prompt": {**PRODUCTION_REQUIRED, "citation_grounding": 0.95},
}


def evaluate_summary(
    summary: dict,
    thresholds: dict[str, float] | None = None,
    *,
    require_missing: bool = True,
    llm_enabled: bool | None = None,
) -> tuple[bool, list[str]]:
    checks = dict(thresholds or THRESHOLDS)
    use_llm = llm_available() if llm_enabled is None else llm_enabled
    if use_llm:
        checks = {**checks, **LLM_REQUIRED}
    failed: list[str] = []
    for metric, threshold in checks.items():
        if metric == "faithfulness" and not use_llm:
            continue
        value = summary.get(metric)
        if value is None:
            if require_missing:
                failed.append(f"{metric}=missing < {threshold}")
            continue
        if value < threshold:
            failed.append(f"{metric}={value} < {threshold}")
    if not checks:
        return False, ["no metrics"]
    return not failed, failed


def main(experiment: str = "hybrid-rerank") -> int:
    path = ROOT / "evals" / "experiments" / experiment / "results.json"
    if not path.exists():
        print(f"missing {path}")
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    thresholds = VARIANT_THRESHOLDS.get(experiment, THRESHOLDS)
    passed, failed = evaluate_summary(summary, thresholds)
    if not passed:
        print("QUALITY GATE FAILED:", "; ".join(failed))
        return 1
    print("QUALITY GATE PASSED", summary)
    return 0


if __name__ == "__main__":
    experiment = "hybrid-rerank"
    if "--experiment" in sys.argv:
        experiment = sys.argv[sys.argv.index("--experiment") + 1]
    raise SystemExit(main(experiment))
