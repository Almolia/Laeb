from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from prometheus_client import Histogram
from redis import Redis
from sqlalchemy import select

from app.domain.matching import BookOrder, match_orders
from app.domain.orders import OPEN_STATUSES, status_for
from app.infrastructure.models import BookOrderRow, MatchCycleRow, TradeRow
from shared_kernel.config import settings
from shared_kernel.db import session_factory
from shared_kernel.outbox import enqueue

log = logging.getLogger(__name__)

LOCK_KEY = "trading:match-cycle:lock"
LOCK_TTL_SECONDS = 280
MATCH_CYCLE_DURATION = Histogram(
    "trading_match_cycle_duration_seconds",
    "Duration of the marketplace matching cycle",
)


def _open_item_ids() -> list[str]:
    with session_factory()() as db:
        return list(
            db.execute(
                select(BookOrderRow.item_id)
                .where(BookOrderRow.status.in_(OPEN_STATUSES))
                .distinct()
                .order_by(BookOrderRow.item_id)
            ).scalars()
        )


def _run_for_item(item_id: str) -> int:
    """Run one atomic item-book cycle, committing once for this item."""
    with session_factory()() as db:
        rows = (
            db.execute(
                select(BookOrderRow)
                .where(
                    BookOrderRow.item_id == item_id,
                    BookOrderRow.status.in_(OPEN_STATUSES),
                )
                .order_by(BookOrderRow.id)
                .with_for_update()
            )
            .scalars()
            .all()
        )
        buys = [
            BookOrder(
                id=row.id,
                user_id=row.user_id,
                price_minor=row.price_minor,
                quantity=row.quantity - row.filled,
                created_at=row.created_at.timestamp(),
            )
            for row in rows
            if row.side == "BUY"
        ]
        sells = [
            BookOrder(
                id=row.id,
                user_id=row.user_id,
                price_minor=row.price_minor,
                quantity=row.quantity - row.filled,
                created_at=row.created_at.timestamp(),
            )
            for row in rows
            if row.side == "SELL"
        ]
        matches = match_orders(buys, sells)
        by_id = {row.id: row for row in rows}

        for match in matches:
            buy = by_id[match.buy_order_id]
            sell = by_id[match.sell_order_id]
            buy.filled += match.quantity
            sell.filled += match.quantity
            buy.status = status_for(buy.quantity, buy.filled)
            sell.status = status_for(sell.quantity, sell.filled)

            trade_id = str(uuid.uuid4())
            db.add(
                TradeRow(
                    id=trade_id,
                    item_id=item_id,
                    buy_order_id=buy.id,
                    sell_order_id=sell.id,
                    buyer_id=match.buyer_id,
                    seller_id=match.seller_id,
                    price_minor=match.price_minor,
                    quantity=match.quantity,
                    status="PENDING_PAYMENT",
                )
            )
            enqueue(
                db,
                "trade.matched",
                {
                    "tradeId": trade_id,
                    "itemId": item_id,
                    "buyerId": match.buyer_id,
                    "sellerId": match.seller_id,
                    "priceMinor": match.price_minor,
                    "quantity": match.quantity,
                },
                producer="trading",
            )
        db.commit()
        return len(matches)


def run_match_cycle() -> int:
    """Run matching for every item that currently has an open order."""
    matches_made = 0
    for item_id in _open_item_ids():
        matches_made += _run_for_item(item_id)
    return matches_made


def _record_cycle(
    cycle_id: str,
    started_at: datetime,
    finished_at: datetime,
    matches_made: int,
    duration_ms: int,
) -> None:
    with session_factory()() as db:
        db.add(
            MatchCycleRow(
                id=cycle_id,
                started_at=started_at,
                finished_at=finished_at,
                matches_made=matches_made,
                duration_ms=duration_ms,
            )
        )
        db.commit()


def run_cycle_with_lock() -> dict:
    """Guarded entry point used by both APScheduler and the manual endpoint."""
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is not configured")
    redis = Redis.from_url(settings.redis_url)
    token = str(uuid.uuid4())
    if not redis.set(LOCK_KEY, token, nx=True, ex=LOCK_TTL_SECONDS):
        log.warning("previous match cycle still running; skipping this tick")
        return {"acquired": False, "skipped": True, "matchesMade": 0}

    cycle_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    matches_made = 0
    try:
        matches_made = run_match_cycle()
        return {
            "acquired": True,
            "skipped": False,
            "cycleId": cycle_id,
            "matchesMade": matches_made,
        }
    finally:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.monotonic() - started) * 1000)
        MATCH_CYCLE_DURATION.observe(duration_ms / 1000)
        try:
            _record_cycle(
                cycle_id,
                started_at,
                finished_at,
                matches_made,
                duration_ms,
            )
        except Exception:
            log.exception("failed to record match cycle %s", cycle_id)
        if redis.get(LOCK_KEY) == token.encode():
            redis.delete(LOCK_KEY)
        if duration_ms > 240_000:
            log.error(
                "MATCH CYCLE APPROACHING 5-MINUTE SLA: %d ms", duration_ms
            )


def list_match_cycles(limit: int = 20) -> list[dict]:
    with session_factory()() as db:
        rows = (
            db.execute(
                select(MatchCycleRow)
                .order_by(MatchCycleRow.started_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "cycleId": row.id,
                "startedAt": row.started_at.isoformat(),
                "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
                "matchesMade": row.matches_made,
                "durationMs": row.duration_ms,
            }
            for row in rows
        ]
