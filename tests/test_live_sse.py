import time

from creditlens.agents import nodes
from creditlens.agents.runner import stream_analysis
from creditlens.db import init_db
from creditlens.presets import presets


def test_stream_yields_node_start_before_slow_score(monkeypatch):
    init_db()
    original = nodes.score_application

    def slow(app):
        time.sleep(0.2)
        return original(app)

    monkeypatch.setattr(nodes, "score_application", slow)
    t0 = time.perf_counter()
    marks: list[tuple[str, str | None, float]] = []
    for event in stream_analysis(presets()[0].application, hitl="auto"):
        marks.append((event.type, event.node, time.perf_counter() - t0))
    start = next(item for item in marks if item[0] == "node_start" and item[1] == "calculate_score")
    end = next(item for item in marks if item[0] == "node_end" and item[1] == "calculate_score")
    assert end[2] - start[2] >= 0.15
    assert any(item[0] == "done" for item in marks)


def test_span_duration_covers_node_work(monkeypatch):
    init_db()
    original = nodes.score_application

    def slow(app):
        time.sleep(0.15)
        return original(app)

    monkeypatch.setattr(nodes, "score_application", slow)
    from creditlens.agents.runner import run_analysis
    from creditlens.observability.factory import get_observability

    run_id, _state, _events = run_analysis(presets()[0].application, hitl="auto")
    trace = get_observability().get_trace_by_run(run_id)
    assert trace is not None
    span = next(item for item in trace.spans if item.name == "calculate_score")
    assert (span.duration_ms or 0) >= 140
