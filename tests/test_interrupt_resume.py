from creditlens.agents.runner import run_analysis, stream_analysis
from creditlens.db import init_db
from creditlens.presets import preset_by_id


def test_manual_preset_interrupts_then_resumes():
    init_db()
    preset = preset_by_id("zeta-manual")
    assert preset is not None
    events = list(stream_analysis(preset.application, hitl="interrupt"))
    assert any(event.type == "interrupt" for event in events)
    assert not any(event.type == "done" for event in events)
    run_id = events[0].run_id
    resumed = list(stream_analysis(run_id=run_id, resume="approve", hitl="interrupt"))
    assert any(event.type == "done" for event in resumed)


def test_auto_hitl_completes_manual_preset():
    init_db()
    preset = preset_by_id("zeta-manual")
    assert preset is not None
    run_id, state, events = run_analysis(preset.application, hitl="auto")
    assert run_id
    assert state.get("recommendation") is not None
    assert state["recommendation"].score == state["scoring"].score
    assert any(event.type == "done" for event in events)
