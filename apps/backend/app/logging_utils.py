"""Logging utilities for the demo backend.

Goals:
- Consistent log format across app modules
- Request-scoped request_id for easier tracing
- Simple env-based log level control
"""

from __future__ import annotations

import contextvars
import logging
import os
from typing import Optional


REQUEST_ID_CTX: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject request_id into every LogRecord (best-effort)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 (Filter.filter)
        # Uvicorn / third-party logs also pass here; make sure attribute exists.
        record.request_id = REQUEST_ID_CTX.get("-")
        return True


def _parse_log_level(level_name: Optional[str]) -> int:
    if not level_name:
        return logging.INFO
    name = level_name.strip().upper()
    return getattr(logging, name, logging.INFO)


def configure_logging() -> None:
    """Configure Python logging for the demo backend.

    Controlled by env:
    - FAIRY_DEMO_LOG_LEVEL: DEBUG/INFO/WARNING/ERROR (default INFO)
    """

    level = _parse_log_level(os.getenv("FAIRY_DEMO_LOG_LEVEL", "INFO"))

    # Keep format compact but information-rich (module + line is very helpful for debugging).
    fmt = "%(asctime)s %(levelname)s %(name)s:%(lineno)d [rid=%(request_id)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=fmt, datefmt=datefmt)
    else:
        root.setLevel(level)
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        for h in root.handlers:
            h.setLevel(level)
            h.setFormatter(formatter)

    # Ensure request_id is present on all records (including uvicorn logs).
    for h in logging.getLogger().handlers:
        if not any(isinstance(f, RequestIdFilter) for f in getattr(h, "filters", [])):
            h.addFilter(RequestIdFilter())

    # Align common loggers with our level (format is handled by handlers above).
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


