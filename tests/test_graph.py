from creditlens.agents.graph import get_graph
from creditlens.agents.nodes import validate_application
from creditlens.agents.runner import run_analysis
from creditlens.db import init_db
from creditlens.presets import presets


def test_graph_compiles():
    graph = get_graph()
    assert "calculate_score" in graph.get_graph().nodes


def test_validation_rejects_young_company():
    app = presets()[0].application.model_copy(update={"company_age_months": 2})
    result = validate_application({"application": app, "node_trace": []})
    assert result["validation"].valid is False


def test_analyze_uses_scoring_tool():
    init_db()
    run_id, state, events = run_analysis(presets()[0].application)
    assert run_id
    assert state["scoring"] is not None
    assert state["recommendation"] is not None
    assert state["recommendation"].score == state["scoring"].score
    assert state["recommendation"].decision == state["scoring"].decision
    assert "calculate_score" in (state.get("node_trace") or [])
    assert any(event.type == "done" for event in events)
