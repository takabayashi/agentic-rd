"""Structured (JSON) logging for the app.

One-line JSON per record so logs are greppable/parseable in aggregation tools
without pulling in a logging framework. Idempotent: safe to call more than once
(the FastAPI lifespan calls it on startup).
"""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    # Replace any existing handlers so re-invocation doesn't double-log.
    root.handlers = [handler]
    root.setLevel(level)
