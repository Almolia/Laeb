"""Catalog worker: outbox publisher + festival event consumer."""
import logging
import threading

from shared_kernel.config import settings
from shared_kernel.db import Base, engine, session_factory
from shared_kernel.events import EventEnvelope, consume
from shared_kernel.inbox import claim
from shared_kernel.logging import setup_logging
from shared_kernel.outbox import run_publisher

from app.application import service as svc
from app.infrastructure import models  # noqa: F401

setup_logging("catalog-worker", settings.log_level)
log = logging.getLogger(__name__)


def handle(env: EventEnvelope) -> None:
    with session_factory()() as db:
        if not claim(db, env.eventId):
            return
        if env.eventName == "festival.started":
            payload = env.payload
            for entry in payload.get("entries", []):
                svc.upsert_discount(
                    db,
                    entry["gameId"],
                    payload["festivalId"],
                    int(entry["discountPercent"]),
                    payload["startsAt"],
                    payload["endsAt"],
                )
            db.commit()
            log.info("applied festival.started festivalId=%s", payload.get("festivalId"))
        elif env.eventName == "festival.ended":
            svc.delete_discounts_for(db, env.payload["festivalId"])
            db.commit()
            log.info("applied festival.ended festivalId=%s", env.payload.get("festivalId"))
        else:
            db.commit()


def _consume_loop() -> None:
    consume(
        queue="q.catalog",
        routing_keys=["festival.started", "festival.ended"],
        handler=handle,
    )


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine())
    log.info("catalog worker started")
    t = threading.Thread(target=_consume_loop, name="catalog-consumer", daemon=True)
    t.start()
    run_publisher()
