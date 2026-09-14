from __future__ import annotations

import json
import sys

from creditlens.config import ROOT

THRESHOLDS = {
    "scoring_consistency": 1.0,
    "citation_precision": 0.25,
    "faithfulness": 0.7,
    "required_tool_usage": 1.0,
    "numeric_consistency": 1.0,
}


def main(experiment: str = "hybrid-rerank") -> int:
    path = ROOT / "evals" / "experiments" / experiment / "results.json"
    if not path.exists():
        print(f"missing {path}")
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    failed = []
    for metric, threshold in THRESHOLDS.items():
        value = summary.get(metric)
        if value is None:
            continue
        if value < threshold:
            failed.append(f"{metric}={value} < {threshold}")
    if failed:
        print("QUALITY GATE FAILED:", "; ".join(failed))
        return 1
    print("QUALITY GATE PASSED", summary)
    return 0


if __name__ == "__main__":
    experiment = "hybrid-rerank"
    if "--experiment" in sys.argv:
        experiment = sys.argv[sys.argv.index("--experiment") + 1]
    raise SystemExit(main(experiment))
