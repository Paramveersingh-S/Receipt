import asyncio
import datetime
import json
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional
import structlog
from sqlmodel import Session, select
import receipt_api.db as db_module
from receipt_api.models import Job

logger = structlog.get_logger(__name__)

HandlerType = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class JobQueue:
    """SQLite-backed persistent background job queue with in-process worker."""

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._handlers: Dict[str, HandlerType] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def register(self, kind: str) -> Callable[[HandlerType], HandlerType]:
        def decorator(handler: HandlerType) -> HandlerType:
            self._handlers[kind] = handler
            return handler
        return decorator

    def enqueue(
        self,
        kind: str,
        payload: Dict[str, Any],
        run_after: Optional[datetime.datetime] = None,
    ) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.datetime.now(datetime.timezone.utc)
        job = Job(
            id=job_id,
            kind=kind,
            payload_json=json.dumps(payload),
            state="queued",
            attempts=0,
            run_after=run_after,
        )
        with Session(db_module.engine) as session:
            session.add(job)
            session.commit()
        return job_id

    async def _claim_next_job(self) -> Optional[Job]:
        now = datetime.datetime.now(datetime.timezone.utc)
        with Session(db_module.engine) as session:
            statement = (
                select(Job)
                .where(Job.state == "queued")
                .where((Job.run_after == None) | (Job.run_after <= now))
                .order_by(Job.id.asc())
                .limit(1)
            )
            job = session.exec(statement).first()
            if not job:
                return None

            job.state = "running"
            job.locked_by = self.worker_id
            job.attempts += 1
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    async def _process_job(self, job: Job, timeout_secs: float = 300.0) -> None:
        handler = self._handlers.get(job.kind)
        if not handler:
            logger.error("No handler registered for job", kind=job.kind, job_id=job.id)
            with Session(db_module.engine) as session:
                j = session.get(Job, job.id)
                if j:
                    j.state = "failed"
                    session.add(j)
                    session.commit()
            return

        payload = json.loads(job.payload_json)
        try:
            await asyncio.wait_for(handler(payload), timeout=timeout_secs)
            with Session(db_module.engine) as session:
                j = session.get(Job, job.id)
                if j:
                    j.state = "completed"
                    j.locked_by = None
                    session.add(j)
                    session.commit()
        except Exception as e:
            logger.exception("Job execution failed", job_id=job.id, error=str(e))
            with Session(db_module.engine) as session:
                j = session.get(Job, job.id)
                if j:
                    if j.attempts >= 3:
                        j.state = "failed"
                    else:
                        j.state = "queued"
                    j.locked_by = None
                    session.add(j)
                    session.commit()

    async def start_worker(self, poll_interval: float = 0.5) -> None:
        self._running = True
        logger.info("Starting background job worker", worker_id=self.worker_id)
        while self._running:
            try:
                job = await self._claim_next_job()
                if job:
                    await self._process_job(job)
                else:
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker loop exception", error=str(e))
                await asyncio.sleep(poll_interval)

    def stop_worker(self) -> None:
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()


job_queue = JobQueue()
