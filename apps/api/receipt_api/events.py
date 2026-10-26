import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlmodel import Session, select
import receipt_api.db as db_module
from receipt_api.models import RunEvent


class EventBus:
    """In-process asynchronous publish/subscribe bus for real-time SSE streaming."""

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        async with self._lock:
            q: asyncio.Queue = asyncio.Queue()
            if run_id not in self._subscribers:
                self._subscribers[run_id] = []
            self._subscribers[run_id].append(q)
            return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            if run_id in self._subscribers:
                if q in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(q)
                if not self._subscribers[run_id]:
                    del self._subscribers[run_id]

    async def publish(self, run_id: str, event_dict: Dict[str, Any]) -> None:
        async with self._lock:
            if run_id in self._subscribers:
                for q in self._subscribers[run_id]:
                    await q.put(event_dict)


event_bus = EventBus()


def record_event(run_id: str, event_type: str, payload: Dict[str, Any]) -> RunEvent:
    """Synchronously record an event to the SQLite database with the next sequence number."""
    now = datetime.now(timezone.utc)
    with Session(db_module.engine) as session:
        # Determine next sequence number for this run
        statement = (
            select(RunEvent.seq)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.seq.desc())
            .limit(1)
        )
        last_seq = session.exec(statement).first() or 0
        next_seq = last_seq + 1

        db_event = RunEvent(
            run_id=run_id,
            seq=next_seq,
            type=event_type,
            payload_json=json.dumps(payload),
            at=now,
        )
        session.add(db_event)
        session.commit()
        session.refresh(db_event)
        return db_event


def emit_event(
    run_id: str,
    event_type: str,
    payload: Dict[str, Any],
    session: Optional[Session] = None,
) -> RunEvent:
    """Record and emit an event to the database with optional session."""
    if session is not None:
        now = datetime.now(timezone.utc)
        statement = (
            select(RunEvent.seq)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.seq.desc())
            .limit(1)
        )
        last_seq = session.exec(statement).first() or 0
        db_event = RunEvent(
            run_id=run_id,
            seq=last_seq + 1,
            type=event_type,
            payload_json=json.dumps(payload),
            at=now,
        )
        session.add(db_event)
        session.commit()
        session.refresh(db_event)
        return db_event
    return record_event(run_id, event_type, payload)


async def publish_event(run_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist event to database and dispatch to all active live subscribers."""
    loop = asyncio.get_event_loop()
    db_event = await loop.run_in_executor(None, record_event, run_id, event_type, payload)

    event_data = {
        "seq": db_event.seq,
        "type": db_event.type,
        "at": db_event.at.isoformat(),
        "payload": payload,
    }
    await event_bus.publish(run_id, event_data)
    return event_data


async def stream_run_events(
    run_id: str, after_seq: int = 0
) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream persisted historical events followed by live events."""
    # 1. Fetch persisted historical events
    with Session(db_module.engine) as session:
        statement = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq.asc())
        )
        historical_events = session.exec(statement).all()

    last_yielded_seq = after_seq
    run_is_complete = False

    for ev in historical_events:
        yield {
            "seq": ev.seq,
            "type": ev.type,
            "at": ev.at.isoformat() if hasattr(ev.at, "isoformat") else str(ev.at),
            "payload": json.loads(ev.payload_json),
        }
        last_yielded_seq = ev.seq
        if ev.type in ("run.finished", "run.failed"):
            run_is_complete = True

    if run_is_complete:
        return

    # 2. Subscribe to live events
    q = await event_bus.subscribe(run_id)
    try:
        while True:
            try:
                event_data = await asyncio.wait_for(q.get(), timeout=30.0)
                if event_data["seq"] > last_yielded_seq:
                    last_yielded_seq = event_data["seq"]
                    yield event_data
                    if event_data["type"] in ("run.finished", "run.failed"):
                        break
            except asyncio.TimeoutError:
                # Keep-alive ping
                yield {"seq": last_yielded_seq, "type": "ping", "at": datetime.now(timezone.utc).isoformat(), "payload": {}}
    finally:
        await event_bus.unsubscribe(run_id, q)
