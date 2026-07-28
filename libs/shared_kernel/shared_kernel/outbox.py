import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base, session_factory
from .events import EventEnvelope, publish
from .logging import correlation_id

log = logging.getLogger(__name__)


class OutboxMessage(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_name: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB)
    correlation_id: Mapped[str] = mapped_column(String(64), default="-")
    producer: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def enqueue(session: Session, event_name: str, payload: dict, producer: str) -> None:
    """Call INSIDE the same transaction as your state change. Do not commit here."""
    session.add(
        OutboxMessage(
            event_name=event_name,
            payload=payload,
            producer=producer,
            correlation_id=correlation_id.get(),
        )
    )


def run_publisher(poll_seconds: float = 1.0) -> None:
    """Runs forever in worker.py."""
    factory = session_factory()
    while True:
        try:
            with factory() as db:
                rows = (
                    db.execute(
                        select(OutboxMessage)
                        .where(OutboxMessage.published_at.is_(None))
                        .order_by(OutboxMessage.created_at)
                        .limit(100)
                        .with_for_update(skip_locked=True)
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    publish(
                        EventEnvelope(
                            eventId=row.id,
                            eventName=row.event_name,
                            payload=row.payload,
                            correlationId=row.correlation_id,
                            producer=row.producer,
                        )
                    )
                    row.published_at = datetime.now(timezone.utc)
                db.commit()
                if rows:
                    log.info("published %d outbox messages", len(rows))
        except Exception:
            log.exception("outbox publisher cycle failed")
        time.sleep(poll_seconds)
