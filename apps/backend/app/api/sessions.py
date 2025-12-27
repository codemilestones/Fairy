from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.models import CreateSessionResponse, SessionReadResponse
from app.runtime import get_store


router = APIRouter(prefix="/api", tags=["sessions"])


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    store = get_store()
    session_id = uuid.uuid4().hex
    store.create_session(session_id)
    return CreateSessionResponse(session_id=session_id)


@router.get("/sessions/{session_id}", response_model=SessionReadResponse)
def read_session(session_id: str) -> SessionReadResponse:
    store = get_store()
    try:
        session = store.get_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SessionReadResponse(session=session)


