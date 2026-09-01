import logging
import os

from openinference.instrumentation import TracerProvider
from phoenix.otel import register

logger = logging.getLogger(__name__)


def configure_tracing() -> TracerProvider:
    """Otel for phoenix observability platform."""

    if not os.getenv("PHOENIX_COLLECTOR_ENDPOINT"):
        raise KeyError("PHOENIX_COLLECTOR_ENDPOINT envvar not set.")
    tracer_provider = register(
        project_name="travel-agent", auto_instrument=True, batch=True
    )

    logger.info(
        "tracing enabled", extra={"collector": os.environ["PHOENIX_COLLECTOR_ENDPOINT"]}
    )
    return tracer_provider
