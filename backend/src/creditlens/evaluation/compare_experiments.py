from __future__ import annotations

import json

from creditlens.db import init_db
from creditlens.evaluation.quality_gate import VARIANT_THRESHOLDS, evaluate_summary
from creditlens.evaluation.runner import latest_by_variant


def main() -> None:
    init_db()
    payload = latest_by_variant()
    for name, row in payload.items():
        passed, failed = evaluate_summary(row["summary"], VARIANT_THRESHOLDS.get(name))
        print(name, "PASS" if passed else "FAIL", json.dumps(row["summary"], ensure_ascii=False), failed)


if __name__ == "__main__":
    main()
