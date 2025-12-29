"""In-memory pub/sub for SSE subscribers (demo-only, single-process)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict


logger = logging.getLogger(__name__)


@dataclass(eq=False)
class Subscriber:
    queue: "asyncio.Queue[dict[str, Any]]"


class SessionPubSub:
    def __init__(self) -> None:
        self._subs: Dict[str, set[Subscriber]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> Subscriber:
        sub = Subscriber(queue=asyncio.Queue(maxsize=200))
        async with self._lock:
            self._subs.setdefault(session_id, set()).add(sub)
            logger.debug("pubsub subscribe session_id=%s subs=%d", session_id, len(self._subs.get(session_id, set())))
        return sub

    async def unsubscribe(self, session_id: str, sub: Subscriber) -> None:
        async with self._lock:
            subs = self._subs.get(session_id)
            if not subs:
                return
            subs.discard(sub)
            if not subs:
                self._subs.pop(session_id, None)
            logger.debug("pubsub unsubscribe session_id=%s remaining=%d", session_id, len(self._subs.get(session_id, set())))

    async def publish(self, session_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subs.get(session_id, set()))
        if subs:
            logger.debug("pubsub publish session_id=%s fanout=%d type=%s", session_id, len(subs), message.get("type"))
        for sub in subs:
            try:
                sub.queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop if slow consumer (demo)
                logger.warning("pubsub drop (queue full) session_id=%s", session_id)
                pass

    async def stream(self, session_id: str, sub: Subscriber) -> AsyncIterator[dict[str, Any]]:
        while True:
            msg = await sub.queue.get()
            yield msg


