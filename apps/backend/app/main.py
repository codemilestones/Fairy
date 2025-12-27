from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.messages import router as messages_router
from app.api.sessions import router as sessions_router
from app.runtime import get_store


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(title="Fairy Demo Backend", version="0.1.0")

    # Ensure DB initialized
    get_store()

    # CORS
    cors_env = os.getenv("FAIRY_DEMO_CORS_ORIGINS", "")
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    if not allow_origins:
        allow_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(sessions_router)
    app.include_router(messages_router)
    app.include_router(events_router)

    return app


app = create_app()


