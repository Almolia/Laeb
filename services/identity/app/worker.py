"""Background process: RabbitMQ consumers + outbox publisher + schedulers."""
import logging
import time

from shared_kernel.config import settings
from shared_kernel.logging import setup_logging

setup_logging("identity-worker", settings.log_level)
log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.info("worker started")
    while True:
        time.sleep(5)
