from openinference.instrumentation import TracerProvider
import logging
from opentelemetry.trace import Tracer
from phoenix.otel import register
from opentelemetry import trace
import os

logger = logging.getLogger(__name__)


def configure_tracing() -> TracerProvider:
    """Otel for phoenix observability platform."""

    if not os.getenv("PHOENIX_COLLECTOR_ENDPOINT"):
        raise KeyError("PHOENIX_COLLECTOR_ENDPOINT envvar not set.")
    tracer_provider = register(project_name="travel-agent", auto_instrument=True)

    logger.info(
        "tracing enabled", extra={"collector": os.environ["PHOENIX_COLLECTOR_ENDPOINT"]}
    )
    return tracer_provider
