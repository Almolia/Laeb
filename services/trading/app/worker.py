"""Trading worker: scheduler plus transactional outbox publisher."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import start_http_server

from app.application.matching_cycle import run_cycle_with_lock
from app.infrastructure import models  # noqa: F401
from shared_kernel.config import settings
from shared_kernel.db import Base, engine
from shared_kernel.logging import setup_logging
from shared_kernel.outbox import OutboxMessage, run_publisher  # noqa: F401

setup_logging("trading-worker", settings.log_level)
log = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cycle_with_lock,
        "interval",
        minutes=5,
        id="match-cycle",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine())
    start_http_server(9107)
    scheduler = build_scheduler()
    scheduler.start()
    log.info("trading worker started; matching every five minutes")
    run_publisher()
