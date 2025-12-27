"""Runtime singletons (store, pubsub) for the demo backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.realtime.pubsub import SessionPubSub
from app.storage.sqlite import SQLiteStore


_store: Optional[SQLiteStore] = None
_pubsub: Optional[SessionPubSub] = None


def get_store() -> SQLiteStore:
    global _store
    if _store is None:
        db_path = os.getenv("FAIRY_DEMO_DB_PATH")
        if db_path:
            path = Path(db_path)
        else:
            path = Path(__file__).resolve().parents[2] / "var" / "fairy_demo.sqlite3"
        _store = SQLiteStore(db_path=path)
        _store.init()
    return _store


def get_pubsub() -> SessionPubSub:
    global _pubsub
    if _pubsub is None:
        _pubsub = SessionPubSub()
    return _pubsub


