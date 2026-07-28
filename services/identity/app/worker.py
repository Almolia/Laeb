"""Background process: outbox publisher only (Identity consumes no events)."""
import logging

from shared_kernel.config import settings
from shared_kernel.db import Base, engine
from shared_kernel.logging import setup_logging
from shared_kernel.outbox import OutboxMessage, run_publisher  # noqa: F401

from app.infrastructure import models  # noqa: F401 — registers tables

setup_logging("identity-worker", settings.log_level)
log = logging.getLogger(__name__)

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine())
    log.info("identity worker started — outbox publisher")
    run_publisher()
