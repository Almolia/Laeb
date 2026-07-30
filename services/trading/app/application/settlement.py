from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.domain.orders import status_for
from app.domain.settlement import compensate_failed_sell
from app.infrastructure.models import BookOrderRow, HoldingRow, TradeRow
from shared_kernel.db import session_factory
from shared_kernel.events import EventEnvelope
from shared_kernel.errors import AppError
from shared_kernel.inbox import claim
from shared_kernel.outbox import enqueue

log = logging.getLogger(__name__)


def _locked_holding(db, user_id: str, item_id: str) -> HoldingRow | None:
    return db.execute(
        select(HoldingRow)
        .where(HoldingRow.user_id == user_id, HoldingRow.item_id == item_id)
        .with_for_update()
    ).scalar_one_or_none()


def handle_payment_settled(env: EventEnvelope) -> None:
    payload = env.payload
    trade_id = str(payload.get("tradeId", ""))
    if not trade_id:
        raise AppError("INVALID_EVENT", "tradeId is required", 422)

    with session_factory()() as db:
        if not claim(db, env.eventId):
            return
        trade = db.execute(
            select(TradeRow).where(TradeRow.id == trade_id).with_for_update()
        ).scalar_one_or_none()
        if trade is None or trade.status != "PENDING_PAYMENT":
            db.commit()  # retain the inbox claim for unknown/already handled events
            return

        if bool(payload.get("ok")):
            seller = _locked_holding(db, trade.seller_id, trade.item_id)
            if seller is None or seller.quantity < trade.quantity or seller.reserved < trade.quantity:
                raise AppError(
                    "RESERVATION_INCONSISTENT",
                    "Seller holding cannot satisfy the settled trade",
                    409,
                )
            buyer = _locked_holding(db, trade.buyer_id, trade.item_id)
            if buyer is None:
                buyer = HoldingRow(
                    user_id=trade.buyer_id,
                    item_id=trade.item_id,
                    quantity=0,
                    reserved=0,
                )
                db.add(buyer)

            seller.quantity -= trade.quantity
            seller.reserved -= trade.quantity
            buyer.quantity += trade.quantity
            trade.status = "SETTLED"
            trade.settled_at = datetime.now(timezone.utc)
            enqueue(
                db,
                "trade.settled",
                {
                    "tradeId": trade.id,
                    "itemId": trade.item_id,
                    "buyerId": trade.buyer_id,
                    "sellerId": trade.seller_id,
                    "priceMinor": trade.price_minor,
                    "quantity": trade.quantity,
                },
                producer="trading",
            )
        else:
            seller_holding = _locked_holding(db, trade.seller_id, trade.item_id)
            if seller_holding is None or seller_holding.reserved < trade.quantity:
                raise AppError(
                    "RESERVATION_INCONSISTENT",
                    "Seller reservation cannot be released",
                    409,
                )
            seller_holding.reserved -= trade.quantity

            order_ids = sorted([trade.buy_order_id, trade.sell_order_id])
            orders = (
                db.execute(
                    select(BookOrderRow)
                    .where(BookOrderRow.id.in_(order_ids))
                    .order_by(BookOrderRow.id)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            by_id = {order.id: order for order in orders}
            buy = by_id.get(trade.buy_order_id)
            sell = by_id.get(trade.sell_order_id)
            if buy is None or sell is None:
                raise AppError("ORDER_NOT_FOUND", "Matched order is missing", 409)
            if buy.filled < trade.quantity or sell.filled < trade.quantity:
                raise AppError("ORDER_INCONSISTENT", "Matched order fill is inconsistent", 409)

            buy.filled -= trade.quantity
            buy.status = status_for(buy.quantity, buy.filled)
            compensation = compensate_failed_sell(
                quantity=sell.quantity,
                filled=sell.filled,
                failed_quantity=trade.quantity,
            )
            sell.quantity = compensation.quantity
            sell.filled = compensation.filled
            sell.status = compensation.status
            trade.status = "FAILED"
            log.info(
                "trade payment failed tradeId=%s reason=%s",
                trade.id,
                payload.get("reason"),
            )
        db.commit()
