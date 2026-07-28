import uuid

from sqlalchemy.orm import Session

from app.application.ledger import transfer_users
from app.infrastructure.outbox import enqueue
from app.domain.model import DomainError
from shared_kernel.errors import AppError


def settle_trade(session: Session, payload: dict) -> dict:
    try:
        trade_id = str(payload["tradeId"])
        buyer_id = uuid.UUID(str(payload["buyerId"]))
        seller_id = uuid.UUID(str(payload["sellerId"]))
        price_minor = int(payload.get("priceMinor", payload.get("price")))
        quantity = int(payload.get("quantity", payload.get("qty", 1)))
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("INVALID_TRADE_EVENT", "trade.matched payload is invalid", 400) from exc
    if price_minor < 0 or quantity < 0:
        raise AppError("INVALID_TRADE_EVENT", "Trade amount must not be negative", 400)

    try:
        result = transfer_users(
            session,
            buyer_id,
            seller_id,
            price_minor * quantity,
            reason="TRADE_SETTLEMENT",
            ref_type="TRADE",
            ref_id=trade_id,
        )
        event = {"tradeId": trade_id, "ok": True, "reason": None}
        enqueue(session, "trade.payment_settled", event)
        return event | result
    except (AppError, DomainError) as exc:
        event = {"tradeId": trade_id, "ok": False, "reason": exc.code}
        enqueue(session, "trade.payment_settled", event)
        return event
