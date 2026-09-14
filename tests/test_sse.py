from creditlens.agents.runner import iter_analysis_events, run_analysis
from creditlens.db import get_conn, init_db
from creditlens.presets import presets


def test_analyze_event_order_starts_before_done():
    init_db()
    app = presets()[0].application
    run_id, state, events = run_analysis(app)
    types = [event.type for event in events]
    assert types[0] == "node_start"
    assert types[-1] == "done"
    assert events[0].node == "validate_application"
    assert types.index("node_start") < types.index("done")
    assert any(event.type == "tool" and event.node == "calculate_score" for event in events)
    assert any(event.type == "retrieval" for event in events)
    assert state["scoring"] is not None
    assert run_id


def test_node_start_emitted_while_run_is_still_running():
    init_db()
    app = presets()[0].application

    def sink(event):
        if event.type == "node_start" and event.node == "validate_application":
            row = get_conn().execute("SELECT status FROM runs WHERE run_id=?", (event.run_id,)).fetchone()
            assert row is not None
            assert row["status"] == "running"

    _run_id, _state, events = run_analysis(app, sink=sink)
    assert events[0].type == "node_start"
    assert events[-1].type == "done"


def test_iter_sse_yields_start_before_done():
    init_db()
    app = presets()[0].application
    iterator = iter_analysis_events(app)
    first = next(iterator)
    assert first.type == "node_start"
    assert first.node == "validate_application"
    rest = list(iterator)
    assert rest[-1].type == "done"
    assert any(event.type == "node_end" for event in rest)
