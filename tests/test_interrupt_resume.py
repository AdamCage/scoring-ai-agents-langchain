from creditlens.agents.runner import run_analysis, stream_analysis
from creditlens.db import init_db
from creditlens.presets import preset_by_id


def test_manual_preset_interrupts_then_resumes():
    init_db()
    preset = preset_by_id("zeta-manual")
    assert preset is not None
    events = list(stream_analysis(preset.application, hitl="interrupt"))
    interrupt = next(event for event in events if event.type == "interrupt")
    assert interrupt.data.get("pd") is not None
    assert interrupt.data.get("risk_band")
    assert interrupt.data.get("score") is not None
    assert not any(event.type == "done" for event in events)
    human_end = next(event for event in events if event.type == "node_end" and event.node == "human_review")
    assert human_end.data.get("status") == "interrupt"
    run_id = events[0].run_id
    resumed = list(stream_analysis(run_id=run_id, resume="approve", hitl="interrupt"))
    assert any(event.type == "done" for event in resumed)


def test_request_documents_retrieves_more_then_interrupts_again():
    init_db()
    preset = preset_by_id("zeta-manual")
    assert preset is not None
    events = list(stream_analysis(preset.application, hitl="interrupt"))
    run_id = events[0].run_id
    resumed = list(stream_analysis(run_id=run_id, resume="request_documents", hitl="interrupt"))
    assert any(event.node == "retrieve_more" for event in resumed)
    assert any(event.type == "interrupt" for event in resumed)
    assert not any(event.type == "done" for event in resumed)


def test_auto_hitl_completes_manual_preset():
    init_db()
    preset = preset_by_id("zeta-manual")
    assert preset is not None
    run_id, state, events = run_analysis(preset.application, hitl="auto")
    assert run_id
    assert state.get("recommendation") is not None
    assert state["recommendation"].score == state["scoring"].score
    assert any(event.type == "done" for event in events)
