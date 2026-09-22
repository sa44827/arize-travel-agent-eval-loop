"""Continuous eval scheduler.

Runs run_evals.run_eval_cycle() every EVAL_INTERVAL_SECONDS (default 120s).
Designed to run as a third process alongside:
  1. Phoenix server   (phoenix serve)
  2. Agent API        (uvicorn agent.api:app)

Usage:
    python -m evals.scheduler

The loop is intentionally simple — no external orchestrator needed for the
demo. Production equivalent: Airflow DAG / K8s CronJob / AX online monitors.
"""

import logging
import os
import time

from evals.run_evals import run_cycle as run_eval_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

INTERVAL = int(os.getenv("EVAL_INTERVAL_SECONDS", "120"))


def main() -> None:
    log.info("Eval scheduler started — interval=%ds", INTERVAL)
    log.info("Stop with Ctrl-C.")
    cycle = 0
    while True:
        cycle += 1
        log.info("--- Cycle %d ---", cycle)
        try:
            summary = run_eval_cycle()
            log.info("Cycle %d complete: %s", cycle, summary)
        except KeyboardInterrupt:
            log.info("Scheduler stopped by user.")
            break
        except Exception as e:
            log.error("Cycle %d failed: %s — will retry in %ds", cycle, e, INTERVAL)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
