from __future__ import annotations

import json
import sys

from creditlens.config import ROOT

THRESHOLDS = {
    "scoring_consistency": 1.0,
    "citation_precision": 0.25,
    "citation_grounding": 0.7,
    "required_tool_usage": 1.0,
    "numeric_consistency": 1.0,
}

VARIANT_THRESHOLDS = {
    "vector-only": {**THRESHOLDS, "recall_at_5": 0.55},
    "hybrid": THRESHOLDS,
    "hybrid-rerank": THRESHOLDS,
    "bad-prompt": {**THRESHOLDS, "citation_grounding": 0.95},
}


def evaluate_summary(summary: dict, thresholds: dict[str, float] | None = None) -> tuple[bool, list[str]]:
    failed: list[str] = []
    checked = 0
    for metric, threshold in (thresholds or THRESHOLDS).items():
        value = summary.get(metric)
        if value is None:
            continue
        checked += 1
        if value < threshold:
            failed.append(f"{metric}={value} < {threshold}")
    if checked == 0:
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
