from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def claim(session: Session, event_id: str) -> bool:
    """True = first time, go handle it. False = already processed, skip.
    Call at the START of your handler, inside the handler's transaction."""
    try:
        session.add(ProcessedEvent(event_id=event_id))
        session.flush()
        return True
    except IntegrityError:
        session.rollback()
        return False
