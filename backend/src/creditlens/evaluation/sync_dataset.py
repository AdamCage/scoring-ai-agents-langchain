from __future__ import annotations

import json

from creditlens.config import ROOT
from creditlens.observability.langfuse import _client, available


def main() -> None:
    if not available():
        print("langfuse not configured")
        return
    client = _client()
    if client is None:
        print("langfuse client unavailable")
        return
    datasets = ROOT / "evals" / "datasets"
    for path in datasets.glob("*.jsonl"):
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        name = f"creditlens-{path.stem}"
        try:
            dataset = client.create_dataset(name=name)
        except Exception:
            dataset = None
        for row in rows:
            try:
                client.create_dataset_item(
                    dataset_name=name,
                    input=row,
                    expected_output=row.get("relevant") or row.get("expected_decision"),
                )
            except Exception:
                continue
        print(name, len(rows), getattr(dataset, "id", ""))


if __name__ == "__main__":
    main()
