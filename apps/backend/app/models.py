"""Pydantic models for the Fairy demo backend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    session_id: str


class PostMessageRequest(BaseModel):
    content: str = Field(min_length=1, description="User message content")


class PostMessageResponse(BaseModel):
    session_id: str
    accepted: bool = True


class SessionState(BaseModel):
    """Serializable session state stored in SQLite.

    Keep this permissive for demo; the pipeline writes incremental keys.
    """

    session_id: str
    created_at: datetime
    updated_at: datetime
    status: Literal[
        "new",
        "running",
        "needs_clarification",
        "completed",
        "error",
    ] = "new"

    # Conversation (simple, UI-friendly format)
    messages: list[dict[str, Any]] = Field(default_factory=list)

    # Pipeline artifacts
    intent: Optional[dict[str, Any]] = None
    clarification_question: Optional[str] = None
    research_brief: Optional[str] = None
    compressed_research: Optional[str] = None
    raw_notes: list[str] = Field(default_factory=list)
    final_report: Optional[str] = None

    # Error info
    last_error: Optional[str] = None


class SessionReadResponse(BaseModel):
    session: SessionState


EventType = Literal[
    "intent_detected",
    "scope_clarification_needed",
    "research_brief_ready",
    "research_progress",
    "research_complete",
    "final_report_ready",
    "error",
]


class EventRecord(BaseModel):
    id: int
    session_id: str
    ts: datetime
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


class EventEnvelope(BaseModel):
    """SSE-friendly event envelope."""

    id: int
    type: EventType
    ts: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


