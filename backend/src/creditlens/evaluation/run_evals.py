from __future__ import annotations

import argparse

from creditlens.db import init_db
from creditlens.evaluation.runner import run_evals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", default="hybrid-rerank")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    init_db()
    run = run_evals(experiment=args.experiment, smoke=args.smoke)
    print(run.experiment, run.summary, f"cases={len(run.results)}")


if __name__ == "__main__":
    main()
