from __future__ import annotations

from creditlens.db import init_db
from creditlens.evaluation.runner import run_evals
from creditlens.evaluation.sync_dataset import main as sync_dataset
from creditlens.evaluation.variants import list_variants


def main() -> None:
    init_db()
    sync_dataset()
    for variant in list_variants():
        run = run_evals(experiment=variant.name, smoke=True)
        print(variant.name, run.summary)


if __name__ == "__main__":
    main()
