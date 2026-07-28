import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base
from .errors import AppError


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def _hash(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def replay(session: Session, key: str, body: dict) -> dict | None:
    """Returns the stored response if this key was already used. Raises on key reuse
    with a different body (a real client bug you want to surface loudly)."""
    row = session.get(IdempotencyKey, key)
    if row is None:
        return None
    if row.request_hash != _hash(body):
        raise AppError(
            "IDEMPOTENCY_KEY_REUSED",
            "This Idempotency-Key was used with a different request body",
            409,
        )
    return row.response


def record(session: Session, key: str, body: dict, response: dict) -> None:
    """Call inside the same transaction as the money movement."""
    session.add(
        IdempotencyKey(key=key, request_hash=_hash(body), response=response)
    )
