from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.grants import build_allocations
from app.infrastructure import clients
from app.infrastructure.models import HoldingRow, ItemRow
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
