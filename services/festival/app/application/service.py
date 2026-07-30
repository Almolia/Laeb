from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.lifecycle import started_payload, validate_window
from app.infrastructure import clients
from app.infrastructure.models import FestivalEntryRow, FestivalRow
from shared_kernel.db import session_factory
from shared_kernel.errors import AppError
from shared_kernel.outbox import enqueue


def _entry_dict(row: FestivalEntryRow) -> dict:
    return {
        "festivalId": row.festival_id,
        "gameId": row.game_id,
        "developerId": row.developer_id,
        "discountPercent": row.discount_percent,
        "status": row.status,
        "decidedAt": row.decided_at.isoformat() if row.decided_at else None,
    }


def _festival_dict(db: Session, row: FestivalRow, include_entries: bool = False) -> dict:
    result = {
        "festivalId": row.id,
        "name": row.name,
        "description": row.description,
        "startsAt": row.starts_at.isoformat(),
        "endsAt": row.ends_at.isoformat(),
        "status": row.status,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }
    if include_entries:
        entries = (
            db.execute(
                select(FestivalEntryRow)
                .where(FestivalEntryRow.festival_id == row.id)
                .order_by(FestivalEntryRow.game_id)
            )
            .scalars()
            .all()
        )
        result["entries"] = [_entry_dict(entry) for entry in entries]
    return result


def _load_festival(db: Session, festival_id: str, lock: bool = False) -> FestivalRow:
    if lock:
        row = db.execute(
            select(FestivalRow)
            .where(FestivalRow.id == festival_id)
            .with_for_update()
        ).scalar_one_or_none()
    else:
        row = db.get(FestivalRow, festival_id)
    if row is None:
        raise AppError("FESTIVAL_NOT_FOUND", "Festival not found", 404)
    return row


def create_festival(
    db: Session,
    *,
    name: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    created_by: str,
) -> dict:
    try:
        starts, ends = validate_window(starts_at, ends_at)
    except ValueError as exc:
        raise AppError("INVALID_FESTIVAL_WINDOW", str(exc), 422) from exc
    row = FestivalRow(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        starts_at=starts,
        ends_at=ends,
        status="DRAFT",
        created_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _festival_dict(db, row, include_entries=True)


def add_entry(
    db: Session,
    *,
    festival_id: str,
    game_id: str,
    discount_percent: int,
    authorization: str,
    correlation_id: str | None,
) -> dict:
    festival = _load_festival(db, festival_id, lock=True)
    if festival.status != "DRAFT":
        raise AppError("FESTIVAL_NOT_DRAFT", "Entries can only be added to draft festivals", 409)
    summary = clients.get_game_summary(game_id, authorization, correlation_id)
    developer_id = summary.get("developerId")
    if not developer_id:
        raise AppError("CATALOG_INVALID_RESPONSE", "Game summary has no developerId", 502)
    entry = FestivalEntryRow(
        festival_id=festival_id,
        game_id=game_id,
        developer_id=str(developer_id),
        discount_percent=discount_percent,
        status="PENDING",
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("ENTRY_EXISTS", "This game is already in the festival", 409) from exc
    return _entry_dict(entry)


def list_festivals(db: Session, status: str | None = None) -> list[dict]:
    query = select(FestivalRow)
    if status:
        normalized = status.upper()
        if normalized not in {"DRAFT", "ACTIVE", "ENDED"}:
            raise AppError("INVALID_STATUS", "Unknown festival status", 422)
        query = query.where(FestivalRow.status == normalized)
    rows = (
        db.execute(query.order_by(FestivalRow.starts_at.desc()))
        .scalars()
        .all()
    )
    return [_festival_dict(db, row) for row in rows]


def get_festival(db: Session, festival_id: str) -> dict:
    return _festival_dict(db, _load_festival(db, festival_id), include_entries=True)


def pending_entries(db: Session, developer_id: str) -> list[dict]:
    rows = (
        db.execute(
            select(FestivalEntryRow)
            .where(
                FestivalEntryRow.developer_id == developer_id,
                FestivalEntryRow.status == "PENDING",
            )
            .order_by(FestivalEntryRow.festival_id, FestivalEntryRow.game_id)
        )
        .scalars()
        .all()
    )
    return [_entry_dict(row) for row in rows]


def decide_entry(
    db: Session,
    *,
    festival_id: str,
    game_id: str,
    developer_id: str,
    approve: bool,
) -> dict:
    entry = db.execute(
        select(FestivalEntryRow)
        .where(
            FestivalEntryRow.festival_id == festival_id,
            FestivalEntryRow.game_id == game_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if entry is None:
        raise AppError("ENTRY_NOT_FOUND", "Festival entry not found", 404)
    if entry.developer_id != developer_id:
        raise AppError("FORBIDDEN", "Only the owning developer may decide this entry", 403)
    if entry.status != "PENDING":
        raise AppError("ENTRY_ALREADY_DECIDED", "Festival entry has already been decided", 409)
    entry.status = "APPROVED" if approve else "REJECTED"
    entry.decided_at = datetime.now(timezone.utc)
    db.commit()
    return _entry_dict(entry)


def activate_festival(db: Session, festival_id: str) -> dict:
    festival = _load_festival(db, festival_id, lock=True)
    if festival.status == "ACTIVE":
        return _festival_dict(db, festival, include_entries=True)
    if festival.status != "DRAFT":
        raise AppError("FESTIVAL_NOT_ACTIVATABLE", "Only draft festivals can be activated", 409)
    approved = (
        db.execute(
            select(FestivalEntryRow)
            .where(
                FestivalEntryRow.festival_id == festival_id,
                FestivalEntryRow.status == "APPROVED",
            )
            .order_by(FestivalEntryRow.game_id)
        )
        .scalars()
        .all()
    )
    festival.status = "ACTIVE"
    enqueue(
        db,
        "festival.started",
        started_payload(
            festival_id=festival.id,
            starts_at=festival.starts_at,
            ends_at=festival.ends_at,
            approved_entries=[
                (entry.game_id, entry.discount_percent) for entry in approved
            ],
        ),
        producer="festival",
    )
    db.commit()
    return _festival_dict(db, festival, include_entries=True)


def end_festival(db: Session, festival_id: str) -> dict:
    festival = _load_festival(db, festival_id, lock=True)
    if festival.status == "ENDED":
        return _festival_dict(db, festival, include_entries=True)
    if festival.status != "ACTIVE":
        raise AppError("FESTIVAL_NOT_ACTIVE", "Only active festivals can end", 409)
    festival.status = "ENDED"
    enqueue(
        db,
        "festival.ended",
        {"festivalId": festival.id},
        producer="festival",
    )
    db.commit()
    return _festival_dict(db, festival, include_entries=True)


def run_schedule_tick() -> dict:
    now = datetime.now(timezone.utc)
    with session_factory()() as db:
        activate_ids = list(
            db.execute(
                select(FestivalRow.id).where(
                    FestivalRow.status == "DRAFT", FestivalRow.starts_at <= now
                )
            ).scalars()
        )
        end_ids = list(
            db.execute(
                select(FestivalRow.id).where(
                    FestivalRow.status == "ACTIVE", FestivalRow.ends_at <= now
                )
            ).scalars()
        )

    activated = 0
    ended = 0
    for festival_id in activate_ids:
        with session_factory()() as db:
            try:
                activate_festival(db, festival_id)
                activated += 1
            except AppError as exc:
                if exc.code != "FESTIVAL_NOT_ACTIVATABLE":
                    raise
    for festival_id in end_ids:
        with session_factory()() as db:
            try:
                end_festival(db, festival_id)
                ended += 1
            except AppError as exc:
                if exc.code != "FESTIVAL_NOT_ACTIVE":
                    raise
    return {"activated": activated, "ended": ended}
