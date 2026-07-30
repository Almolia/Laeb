from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.grants import build_allocations
from app.domain.orders import OPEN_STATUSES, available_items, remaining, status_for
from app.infrastructure import clients
from app.infrastructure.models import BookOrderRow, HoldingRow, ItemRow, TradeRow
from shared_kernel.errors import AppError
from shared_kernel.outbox import enqueue


def _item_dict(row: ItemRow) -> dict:
    return {
        "itemId": row.id,
        "gameId": row.game_id,
        "developerId": row.developer_id,
        "name": row.name,
        "description": row.description,
        "iconUrl": row.icon_url,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _holding_dict(row: HoldingRow) -> dict:
    return {
        "userId": row.user_id,
        "itemId": row.item_id,
        "quantity": row.quantity,
        "reserved": row.reserved,
        "available": row.quantity - row.reserved,
    }


def _load_item(db: Session, item_id: str) -> ItemRow:
    row = db.get(ItemRow, item_id)
    if row is None:
        raise AppError("ITEM_NOT_FOUND", "Item not found", 404)
    return row


def _ensure_item_owner(item: ItemRow, developer_id: str) -> None:
    if item.developer_id != developer_id:
        raise AppError("FORBIDDEN", "Only the owning developer may manage this item", 403)


def create_item(
    db: Session,
    *,
    developer_id: str,
    game_id: str,
    name: str,
    description: str | None,
    icon_url: str | None,
    authorization: str,
    correlation_id: str | None,
) -> dict:
    summary = clients.get_game_summary(game_id, authorization, correlation_id)
    if summary.get("developerId") != developer_id:
        raise AppError("FORBIDDEN", "Only the owning developer may create game items", 403)

    row = ItemRow(
        id=str(uuid.uuid4()),
        game_id=game_id,
        developer_id=developer_id,
        name=name,
        description=description,
        icon_url=icon_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_dict(row)


def list_game_items(db: Session, game_id: str) -> list[dict]:
    rows = (
        db.execute(
            select(ItemRow)
            .where(ItemRow.game_id == game_id)
            .order_by(ItemRow.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [_item_dict(row) for row in rows]


def get_item(db: Session, item_id: str) -> dict:
    return _item_dict(_load_item(db, item_id))


def grant_item(
    db: Session,
    *,
    item_id: str,
    developer_id: str,
    authorization: str,
    correlation_id: str | None,
    recipient_mode: str,
    user_ids: list[str] | None,
    user_count: int | None,
    quantity_mode: str,
    quantity: int | None,
    min_quantity: int | None,
    max_quantity: int | None,
    seed: int | None,
) -> dict:
    item = _load_item(db, item_id)
    _ensure_item_owner(item, developer_id)

    requested_ids = list(dict.fromkeys(user_ids or []))
    if recipient_mode.upper() == "EXPLICIT":
        users = clients.get_users(
            authorization, correlation_id, user_ids=requested_ids
        )
    else:
        users = clients.get_users(authorization, correlation_id)
    candidates = [str(user["userId"]) for user in users if user.get("userId")]

    try:
        allocations = build_allocations(
            recipient_mode=recipient_mode,
            candidate_user_ids=candidates,
            explicit_user_ids=requested_ids,
            user_count=user_count,
            quantity_mode=quantity_mode,
            quantity=quantity,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            seed=seed,
        )
    except ValueError as exc:
        raise AppError("INVALID_GRANT", str(exc), 422) from exc

    results: list[dict] = []
    for allocation in allocations:
        holding = db.execute(
            select(HoldingRow)
            .where(
                HoldingRow.user_id == allocation.user_id,
                HoldingRow.item_id == item_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if holding is None:
            holding = HoldingRow(
                user_id=allocation.user_id,
                item_id=item_id,
                quantity=0,
                reserved=0,
            )
            db.add(holding)
        holding.quantity += allocation.quantity
        enqueue(
            db,
            "item.granted",
            {
                "itemId": item.id,
                "gameId": item.game_id,
                "userId": allocation.user_id,
                "quantity": allocation.quantity,
            },
            producer="trading",
        )
        results.append(
            {"userId": allocation.user_id, "quantity": allocation.quantity}
        )

    db.commit()
    return {"itemId": item.id, "grants": results}


def inventory(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.execute(
            select(HoldingRow)
            .where(HoldingRow.user_id == user_id)
            .order_by(HoldingRow.item_id.asc())
        )
        .scalars()
        .all()
    )
    return [_holding_dict(row) for row in rows]



def _order_dict(row: BookOrderRow) -> dict:
    return {
        "orderId": row.id,
        "itemId": row.item_id,
        "userId": row.user_id,
        "side": row.side,
        "priceMinor": row.price_minor,
        "quantity": row.quantity,
        "filled": row.filled,
        "remaining": remaining(row.quantity, row.filled),
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _trade_dict(row: TradeRow) -> dict:
    return {
        "tradeId": row.id,
        "itemId": row.item_id,
        "buyOrderId": row.buy_order_id,
        "sellOrderId": row.sell_order_id,
        "buyerId": row.buyer_id,
        "sellerId": row.seller_id,
        "priceMinor": row.price_minor,
        "quantity": row.quantity,
        "status": row.status,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "settledAt": row.settled_at.isoformat() if row.settled_at else None,
    }


def place_buy_order(
    db: Session, *, user_id: str, item_id: str, price_minor: int, quantity: int
) -> dict:
    _load_item(db, item_id)
    row = BookOrderRow(
        id=str(uuid.uuid4()),
        item_id=item_id,
        user_id=user_id,
        side="BUY",
        price_minor=price_minor,
        quantity=quantity,
        filled=0,
        status="OPEN",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _order_dict(row)


def place_sell_order(
    db: Session, *, user_id: str, item_id: str, price_minor: int, quantity: int
) -> dict:
    _load_item(db, item_id)
    holding = db.execute(
        select(HoldingRow)
        .where(HoldingRow.user_id == user_id, HoldingRow.item_id == item_id)
        .with_for_update()
    ).scalar_one_or_none()
    if holding is None:
        raise AppError(
            "INSUFFICIENT_ITEMS",
            f"You have 0 available, tried to sell {quantity}",
            409,
        )
    available = available_items(holding.quantity, holding.reserved)
    if available < quantity:
        raise AppError(
            "INSUFFICIENT_ITEMS",
            f"You have {available} available, tried to sell {quantity}",
            409,
        )
    holding.reserved += quantity
    row = BookOrderRow(
        id=str(uuid.uuid4()),
        item_id=item_id,
        user_id=user_id,
        side="SELL",
        price_minor=price_minor,
        quantity=quantity,
        filled=0,
        status="OPEN",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _order_dict(row)


def list_my_orders(db: Session, user_id: str, status: str | None = None) -> list[dict]:
    query = select(BookOrderRow).where(BookOrderRow.user_id == user_id)
    if status:
        normalized = status.upper()
        if normalized not in {"OPEN", "PARTIAL", "FILLED", "CANCELLED"}:
            raise AppError("INVALID_STATUS", "Unknown order status", 422)
        query = query.where(BookOrderRow.status == normalized)
    rows = (
        db.execute(query.order_by(BookOrderRow.created_at.desc()))
        .scalars()
        .all()
    )
    return [_order_dict(row) for row in rows]


def cancel_order(db: Session, order_id: str, user_id: str) -> dict:
    row = db.execute(
        select(BookOrderRow).where(BookOrderRow.id == order_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise AppError("ORDER_NOT_FOUND", "Order not found", 404)
    if row.user_id != user_id:
        raise AppError("FORBIDDEN", "Only the order owner may cancel it", 403)
    if row.status not in OPEN_STATUSES:
        raise AppError("ORDER_NOT_CANCELLABLE", "Only open or partial orders can be cancelled", 409)

    if row.side == "SELL":
        amount_to_release = remaining(row.quantity, row.filled)
        holding = db.execute(
            select(HoldingRow)
            .where(HoldingRow.user_id == user_id, HoldingRow.item_id == row.item_id)
            .with_for_update()
        ).scalar_one_or_none()
        if holding is None or holding.reserved < amount_to_release:
            raise AppError("RESERVATION_INCONSISTENT", "Sell reservation is inconsistent", 409)
        holding.reserved -= amount_to_release
    row.status = "CANCELLED"
    db.commit()
    return _order_dict(row)


def orderbook(db: Session, item_id: str) -> dict:
    _load_item(db, item_id)

    def side_rows(side: str):
        ordering = BookOrderRow.price_minor.desc() if side == "BUY" else BookOrderRow.price_minor.asc()
        return db.execute(
            select(
                BookOrderRow.price_minor,
                func.sum(BookOrderRow.quantity - BookOrderRow.filled),
            )
            .where(
                BookOrderRow.item_id == item_id,
                BookOrderRow.side == side,
                BookOrderRow.status.in_(OPEN_STATUSES),
            )
            .group_by(BookOrderRow.price_minor)
            .order_by(ordering)
        ).all()

    return {
        "itemId": item_id,
        "buys": [
            {"priceMinor": price, "quantity": int(qty)} for price, qty in side_rows("BUY")
        ],
        "sells": [
            {"priceMinor": price, "quantity": int(qty)} for price, qty in side_rows("SELL")
        ],
    }


def trade_history(
    db: Session, *, item_id: str | None = None, limit: int = 50
) -> list[dict]:
    query = select(TradeRow)
    if item_id:
        query = query.where(TradeRow.item_id == item_id)
    rows = (
        db.execute(query.order_by(TradeRow.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [_trade_dict(row) for row in rows]
