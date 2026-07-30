from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db import Base
from shared_kernel.outbox import OutboxMessage  # noqa: F401


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FestivalRow(Base):
    __tablename__ = "festivals"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_festival_valid_window"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','ENDED')", name="ck_festival_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="DRAFT")
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )


class FestivalEntryRow(Base):
    __tablename__ = "festival_entries"
    __table_args__ = (
        CheckConstraint(
            "discount_percent BETWEEN 0 AND 100", name="ck_entry_discount_range"
        ),
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_festival_entry_status",
        ),
    )

    festival_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("festivals.id"), primary_key=True
    )
    game_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    developer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="PENDING")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
