import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# First-party packages: these get the requested log level. Everything else
# (httpx, openai, pydantic_ai, ...) defaults to WARNING so noisy third-party
# INFO/DEBUG logs (e.g. one line per HTTP request) don't drown out our own.
_FIRST_PARTY_LOGGERS = ("backend", "agent")


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the root logger to emit JSON lines on stderr.

    Call this once from an application entrypoint (e.g. the CLI's ``main``).
    Library modules should only call ``logging.getLogger(__name__)`` and
    never configure handlers themselves.
    """
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.WARNING)

    for name in _FIRST_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(level)
