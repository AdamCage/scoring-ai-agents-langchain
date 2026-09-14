from __future__ import annotations

import argparse
import json

from creditlens.db import init_db
from creditlens.observability.factory import get_observability


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a local CreditLens trace")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    init_db()
    obs = get_observability()
    if args.run_id:
        trace = obs.get_trace_by_run(args.run_id)
        traces = [trace] if trace else []
    else:
        traces = obs.list_traces(args.limit)
    for trace in traces:
        print(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
