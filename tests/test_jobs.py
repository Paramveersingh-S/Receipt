import asyncio
import pytest
from receipt_api.db import init_db
from receipt_api.jobs import JobQueue


@pytest.mark.asyncio
async def test_job_queue_enqueue_and_process():
    init_db()
    queue = JobQueue(worker_id="test_worker_1")
    processed_payloads = []

    @queue.register("echo_job")
    async def handle_echo(payload):
        processed_payloads.append(payload)

    job_id = queue.enqueue("echo_job", {"message": "hello world"})
    assert job_id.startswith("job_")

    # Claim and execute job
    job = await queue._claim_next_job()
    assert job is not None
    assert job.id == job_id
    assert job.state == "running"

    await queue._process_job(job)
    assert len(processed_payloads) == 1
    assert processed_payloads[0]["message"] == "hello world"


@pytest.mark.asyncio
async def test_job_retry_on_failure():
    init_db()
    queue = JobQueue(worker_id="test_worker_2")

    @queue.register("failing_job")
    async def handle_failing(payload):
        raise RuntimeError("Simulated failure")

    job_id = queue.enqueue("failing_job", {"attempt": 1})
    job = await queue._claim_next_job()
    assert job is not None
    await queue._process_job(job)

    # Job should be put back into queued state with incremented attempt
    job_reclaimed = await queue._claim_next_job()
    assert job_reclaimed is not None
    assert job_reclaimed.id == job_id
    assert job_reclaimed.attempts == 2
