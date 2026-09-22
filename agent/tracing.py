"""One-call Phoenix tracing initialisation.

Call `init_tracing()` once at process start (api.py startup event).
Tracing failures are logged and swallowed — they must never break requests.
"""

import logging
import os

from openinference.instrumentation import OITracer, TraceConfig
from opentelemetry import trace as trace_api

log = logging.getLogger(__name__)

_initialised = False

# Manual spans for our own logic (agent turn, tool calls). The global provider is
# bound lazily by register(); before that (or if tracing is off) spans are no-ops.
tracer = OITracer(trace_api.get_tracer("travel-agent"), TraceConfig())


def init_tracing() -> None:
    """Register Phoenix tracing with google-genai auto-instrumentation.

    Safe to call multiple times (idempotent). The Phoenix server must be
    running at PHOENIX_COLLECTOR_ENDPOINT (default http://localhost:6006)
    before traces will appear, but the agent works fine if it isn't.
    """
    global _initialised
    if _initialised:
        return
    try:
        from phoenix.otel import register

        register(
            project_name=os.getenv("PHOENIX_PROJECT", "travel-agent"),
            auto_instrument=True,  # picks up openinference-instrumentation-google-genai
            batch=True,
        )
        _initialised = True
        log.info("Phoenix tracing initialised (project=%s)", os.getenv("PHOENIX_PROJECT", "travel-agent"))
    except Exception:
        log.warning("Phoenix tracing unavailable — agent continues without it", exc_info=True)
