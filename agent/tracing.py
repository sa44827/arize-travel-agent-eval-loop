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


def init_tracing(project_name: str | None = None) -> None:
    """Register Phoenix tracing with google-genai auto-instrumentation.

    `project_name` defaults to PHOENIX_PROJECT. Callers that run judge calls
    in a separate process (evals/judges.py) pass a distinct "<project>-evals"
    name so agent cost and eval/judge cost land in different Phoenix projects
    and can be reported separately (client asked for both numbers, not one
    combined figure — see docs/BUILD_LOG.md).

    Safe to call multiple times (idempotent per process — the first call wins).
    The Phoenix server must be running at PHOENIX_COLLECTOR_ENDPOINT (default
    http://localhost:6006) before traces will appear, but the caller works
    fine if it isn't.
    """
    global _initialised
    if _initialised:
        return
    name = project_name or os.getenv("PHOENIX_PROJECT", "travel-agent")
    try:
        from phoenix.otel import register

        register(project_name=name, auto_instrument=True, batch=True)
        _initialised = True
        log.info("Phoenix tracing initialised (project=%s)", name)
    except Exception:
        log.warning("Phoenix tracing unavailable — continuing without it", exc_info=True)
