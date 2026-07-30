"""Festival worker: one-minute lifecycle scheduler and outbox publisher."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.application.service import run_schedule_tick
from app.infrastructure import models  # noqa: F401
from shared_kernel.config import settings
from shared_kernel.db import Base, engine
from shared_kernel.logging import setup_logging
from shared_kernel.outbox import OutboxMessage, run_publisher  # noqa: F401

setup_logging("festival-worker", settings.log_level)
log = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_schedule_tick,
        "interval",
        minutes=1,
        id="festival-lifecycle",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine())
    scheduler = build_scheduler()
    scheduler.start()
    log.info("festival worker started; lifecycle check every minute")
    run_publisher()
