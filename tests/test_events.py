import asyncio
import pytest
from receipt_api.db import init_db
from receipt_api.events import event_bus, publish_event, record_event, stream_run_events


@pytest.mark.asyncio
async def test_event_persistence_and_sequence():
    init_db()
    run_id = "run_test_seq_001"

    ev1 = record_event(run_id, "run.started", {"step": 1})
    ev2 = record_event(run_id, "run.step.started", {"name": "testgen"})

    assert ev1.seq == 1
    assert ev2.seq == 2
    assert ev1.run_id == run_id
    assert ev2.run_id == run_id


@pytest.mark.asyncio
async def test_event_streaming_replay():
    init_db()
    run_id = "run_test_stream_002"

    await publish_event(run_id, "run.started", {"status": "init"})
    await publish_event(run_id, "run.step.started", {"step": "prepare"})
    await publish_event(run_id, "run.finished", {"verdict": "VERIFIED"})

    streamed = []
    async for ev in stream_run_events(run_id, after_seq=0):
        streamed.append(ev)

    assert len(streamed) == 3
    assert streamed[0]["seq"] == 1
    assert streamed[0]["type"] == "run.started"
    assert streamed[2]["type"] == "run.finished"


@pytest.mark.asyncio
async def test_event_streaming_with_after_seq():
    init_db()
    run_id = "run_test_stream_after_seq_003"

    await publish_event(run_id, "run.started", {"seq_test": 1})
    await publish_event(run_id, "run.step.started", {"seq_test": 2})
    await publish_event(run_id, "run.finished", {"seq_test": 3})

    streamed = []
    async for ev in stream_run_events(run_id, after_seq=1):
        streamed.append(ev)

    assert len(streamed) == 2
    assert streamed[0]["seq"] == 2
    assert streamed[1]["seq"] == 3
