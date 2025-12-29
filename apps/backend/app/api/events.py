from __future__ import annotations

import json
import asyncio
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.runtime import get_pubsub, get_store


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api", tags=["events"])


def _sse(event: str, data: dict, *, event_id: Optional[int] = None) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


@router.get("/sessions/{session_id}/events")
async def session_events(request: Request, session_id: str, after_id: int = 0):
    """SSE endpoint.

    - Replays events from SQLite after `after_id`
    - Then streams new events from in-memory pubsub
    """
    store = get_store()
    pubsub = get_pubsub()

    # Ensure session exists
    try:
        store.get_session(session_id)
    except KeyError as e:
        logger.warning("sse: session not found session_id=%s", session_id)
        raise HTTPException(status_code=404, detail=str(e)) from e

    logger.info(
        "sse connect session_id=%s after_id=%s client=%s",
        session_id,
        after_id,
        request.client.host if request.client else None,
    )

    async def gen() -> AsyncIterator[bytes]:
        # replay
        replay = store.list_events(session_id, after_id=after_id, limit=500)
        logger.debug("sse replay session_id=%s count=%d after_id=%s", session_id, len(replay), after_id)
        for ev in replay:
            if await request.is_disconnected():
                logger.info("sse disconnected during replay session_id=%s", session_id)
                return
            yield _sse(ev.type, {"ts": ev.ts.isoformat(), "payload": ev.payload}, event_id=ev.id).encode(
                "utf-8"
            )

        # live
        sub = await pubsub.subscribe(session_id)
        try:
            # Periodically wake up to detect disconnect and to keep the connection alive.
            while True:
                if await request.is_disconnected():
                    logger.info("sse disconnected session_id=%s", session_id)
                    return
                try:
                    msg = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # SSE comment as keepalive
                    yield b": keep-alive\n\n"
                    continue
                yield _sse(msg["type"], msg["data"], event_id=msg.get("id")).encode("utf-8")
        finally:
            await pubsub.unsubscribe(session_id, sub)
            logger.debug("sse unsubscribed session_id=%s", session_id)

    return StreamingResponse(gen(), media_type="text/event-stream")


