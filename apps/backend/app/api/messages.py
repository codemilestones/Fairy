from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.models import PostMessageRequest, PostMessageResponse
from app.pipeline.orchestrator import orchestrator
from app.runtime import get_store
from app.storage.sqlite import utc_now


router = APIRouter(prefix="/api", tags=["messages"])


@router.post("/sessions/{session_id}/messages", response_model=PostMessageResponse)
async def post_message(
    session_id: str,
    req: PostMessageRequest,
) -> PostMessageResponse:
    """Append a user message and kick off pipeline processing.

    The actual agent orchestration is implemented in `app.pipeline.orchestrator`.
    """
    store = get_store()
    try:
        session = store.get_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    session.messages.append({"role": "user", "content": req.content})
    session.updated_at = utc_now()
    session.status = "running"
    store.save_session(session)

    # Fire-and-forget in the server event loop (demo).
    asyncio.create_task(orchestrator.safe_run(session_id))

    return PostMessageResponse(session_id=session_id, accepted=True)


