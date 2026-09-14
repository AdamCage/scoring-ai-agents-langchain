from __future__ import annotations

from creditlens.agents.runner import stream_analysis
from creditlens.db import init_db
from creditlens.presets import preset_by_id


def main() -> None:
    init_db()
    preset = preset_by_id("zeta-manual")
    if preset is None:
        raise SystemExit("missing zeta-manual")
    events = list(stream_analysis(preset.application, hitl="interrupt"))
    types = [event.type for event in events]
    print("first", types)
    if "interrupt" not in types:
        raise SystemExit("expected interrupt")
    run_id = events[0].run_id
    resumed = list(stream_analysis(run_id=run_id, resume="approve"))
    print("resume", [event.type for event in resumed])
    if not any(event.type == "done" for event in resumed):
        raise SystemExit("expected done after resume")
    print("ok")


if __name__ == "__main__":
    main()
