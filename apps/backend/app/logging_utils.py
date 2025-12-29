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
from logging.handlers import RotatingFileHandler
from pathlib import Path
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
    - FAIRY_DEMO_LOG_TO_FILE: 1/true/yes to enable file logging (default true)
    - FAIRY_DEMO_LOG_FILE: log file path (default: apps/backend/var/logs/backend.log)
    - FAIRY_DEMO_LOG_MAX_BYTES: rotate when file exceeds this size (default 10MB)
    - FAIRY_DEMO_LOG_BACKUP_COUNT: number of rotated files to keep (default 5)
    """

    level = _parse_log_level(os.getenv("FAIRY_DEMO_LOG_LEVEL", "INFO"))

    # Keep format compact but information-rich (module + line is very helpful for debugging).
    fmt = "%(asctime)s %(levelname)s %(name)s:%(lineno)d [rid=%(request_id)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    request_id_filter = RequestIdFilter()

    if not root.handlers:
        # Default stream handler
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(formatter)
        sh.addFilter(request_id_filter)
        root.addHandler(sh)
        root.setLevel(level)
    else:
        root.setLevel(level)
        for h in root.handlers:
            h.setLevel(level)
            h.setFormatter(formatter)
            if not any(isinstance(f, RequestIdFilter) for f in getattr(h, "filters", [])):
                h.addFilter(request_id_filter)

    # Optional file logging (rotating).
    log_to_file = os.getenv("FAIRY_DEMO_LOG_TO_FILE", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
    if log_to_file:
        # apps/backend/app/logging_utils.py -> parents[1] == apps/backend
        default_path = Path(__file__).resolve().parents[1] / "var" / "logs" / "backend.log"
        file_path = Path(os.getenv("FAIRY_DEMO_LOG_FILE", str(default_path))).expanduser()
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            # If we can't create the directory, skip file logging rather than crashing the app.
            logging.getLogger(__name__).exception("Failed to create log directory: %s", file_path.parent)
        else:
            max_bytes = int(os.getenv("FAIRY_DEMO_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
            backup_count = int(os.getenv("FAIRY_DEMO_LOG_BACKUP_COUNT", "5"))

            # Avoid adding duplicate file handlers on uvicorn reload.
            already = False
            for h in root.handlers:
                if isinstance(h, RotatingFileHandler):
                    try:
                        if Path(getattr(h, "baseFilename", "")) == file_path:
                            already = True
                            break
                    except Exception:
                        pass
            if not already:
                fh = RotatingFileHandler(
                    filename=str(file_path),
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                )
                fh.setLevel(level)
                fh.setFormatter(formatter)
                fh.addFilter(request_id_filter)
                root.addHandler(fh)

    # Align common loggers with our level (format is handled by handlers above).
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)


