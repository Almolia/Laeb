from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared_kernel.db import Base
from shared_kernel.inbox import ProcessedEvent  # noqa: F401
from shared_kernel.outbox import OutboxMessage  # noqa: F401


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ItemRow(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    developer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )


class HoldingRow(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_holdings_quantity_nonnegative"),
        CheckConstraint("reserved >= 0", name="ck_holdings_reserved_nonnegative"),
    )

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BookOrderRow(Base):
    __tablename__ = "book_orders"
    __table_args__ = (
        CheckConstraint("side IN ('BUY','SELL')", name="ck_book_orders_side"),
        CheckConstraint("price_minor > 0", name="ck_book_orders_positive_price"),
        CheckConstraint("quantity > 0", name="ck_book_orders_positive_quantity"),
        CheckConstraint("filled >= 0", name="ck_book_orders_filled_nonnegative"),
        CheckConstraint("filled <= quantity", name="ck_book_orders_filled_lte_quantity"),
        CheckConstraint(
            "status IN ('OPEN','PARTIAL','FILLED','CANCELLED')",
            name="ck_book_orders_status",
        ),
        Index(
            "ix_book_open",
            "item_id",
            "side",
            "status",
            postgresql_where=text("status IN ('OPEN','PARTIAL')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )


class TradeRow(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("price_minor > 0", name="ck_trades_positive_price"),
        CheckConstraint("quantity > 0", name="ck_trades_positive_quantity"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT','SETTLED','FAILED')",
            name="ck_trades_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    buy_order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sell_order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    buyer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    seller_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING_PAYMENT"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=text("now()")
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MatchCycleRow(Base):
    __tablename__ = "match_cycles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    matches_made: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
