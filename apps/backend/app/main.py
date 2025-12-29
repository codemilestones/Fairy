from __future__ import annotations

import logging
import os
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.messages import router as messages_router
from app.api.sessions import router as sessions_router
from app.logging_utils import REQUEST_ID_CTX, configure_logging
from app.runtime import get_store


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    load_dotenv()
    configure_logging()

    app = FastAPI(title="Fairy Demo Backend", version="0.1.0")

    # Ensure DB initialized
    get_store()

    @app.middleware("http")
    async def request_log_middleware(request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = REQUEST_ID_CTX.set(rid)
        start = time.perf_counter()

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "HTTP 完成 method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.exception(
                "HTTP 请求异常 method=%s path=%s query=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                request.url.query,
                duration_ms,
            )
            raise
        finally:
            REQUEST_ID_CTX.reset(token)

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


