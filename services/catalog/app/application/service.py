import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.state_machine import DomainError, GameState, check
from app.infrastructure.models import ActiveDiscountRow, GameRow, GameStateHistoryRow
from shared_kernel.errors import AppError
from shared_kernel.money import apply_discount
from shared_kernel.outbox import enqueue


def _app(exc: DomainError) -> AppError:
    return AppError(exc.code, exc.message, exc.status)


def _refresh_search(db: Session, game_id: str) -> None:
    db.execute(
        text(
            """
            UPDATE games SET search_vector =
              to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,''))
            WHERE id = :gid
            """
        ),
        {"gid": game_id},
    )


def _history(
    db: Session,
    game: GameRow,
    from_state: str | None,
    to_state: str,
    actor_id: str,
    note: str | None = None,
) -> None:
    db.add(
        GameStateHistoryRow(
            id=str(uuid.uuid4()),
            game_id=game.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            note=note,
        )
    )


def _game_dict(g: GameRow) -> dict:
    return {
        "gameId": g.id,
        "developerId": g.developer_id,
        "title": g.title,
        "description": g.description,
        "genre": g.genre,
        "mediaUrls": g.media_urls or [],
        "executableUrl": g.executable_url,
        "basePriceMinor": g.base_price_minor,
        "suggestedPriceMinor": g.suggested_price_minor,
        "state": g.state,
        "createdAt": g.created_at.isoformat() if g.created_at else None,
        "updatedAt": g.updated_at.isoformat() if g.updated_at else None,
    }


def submit_game(
    db: Session,
    developer_id: str,
    title: str,
    description: str,
    genre: str | None,
    media_urls: list[str],
    executable_url: str | None,
) -> dict:
    game_id = str(uuid.uuid4())
    g = GameRow(
        id=game_id,
        developer_id=developer_id,
        title=title,
        description=description or "",
        genre=genre,
        media_urls=media_urls or [],
        executable_url=executable_url,
        state=GameState.SUBMITTED.value,
    )
    db.add(g)
    _history(db, g, None, GameState.SUBMITTED.value, developer_id)
    db.flush()
    _refresh_search(db, game_id)
    db.commit()
    g = db.get(GameRow, game_id)
    return _game_dict(g)


def get_game(db: Session, game_id: str) -> dict:
    g = db.get(GameRow, game_id)
    if not g:
        raise AppError("GAME_NOT_FOUND", "Game not found", 404)
    return _game_dict(g)


def list_games(
    db: Session,
    q: str | None = None,
    genre: str | None = None,
    state: str | None = "Published",
    page: int = 1,
    size: int = 20,
) -> dict:
    query = select(GameRow)
    if state:
        query = query.where(GameRow.state == state)
    if genre:
        query = query.where(GameRow.genre == genre)
    if q:
        query = query.where(
            GameRow.search_vector.op("@@")(func.plainto_tsquery("english", q))
        )
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        db.execute(
            query.order_by(GameRow.created_at.desc())
            .offset(max(page - 1, 0) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "items": [_game_dict(r) for r in rows],
        "page": page,
        "size": size,
        "total": total,
    }


def list_mine(db: Session, developer_id: str) -> list[dict]:
    rows = (
        db.execute(
            select(GameRow)
            .where(GameRow.developer_id == developer_id)
            .order_by(GameRow.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_game_dict(r) for r in rows]


def history(db: Session, game_id: str, actor_id: str, roles: list[str]) -> list[dict]:
    g = db.get(GameRow, game_id)
    if not g:
        raise AppError("GAME_NOT_FOUND", "Game not found", 404)
    if "SUPPORT" not in roles and "ADMIN" not in roles and actor_id != g.developer_id:
        raise AppError("FORBIDDEN", "Not allowed to view history", 403)
    rows = (
        db.execute(
            select(GameStateHistoryRow)
            .where(GameStateHistoryRow.game_id == game_id)
            .order_by(GameStateHistoryRow.at.asc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "fromState": r.from_state,
            "toState": r.to_state,
            "actorId": r.actor_id,
            "note": r.note,
            "at": r.at.isoformat() if r.at else None,
        }
        for r in rows
    ]


def _transition(
    db: Session,
    game_id: str,
    transition: str,
    actor_id: str,
    roles: list[str],
    note: str | None = None,
    suggested_price_minor: int | None = None,
    price_minor: int | None = None,
) -> dict:
    g = db.get(GameRow, game_id)
    if not g:
        raise AppError("GAME_NOT_FOUND", "Game not found", 404)
    try:
        new_state = check(
            transition,
            GameState(g.state),
            roles,
            actor_id,
            g.developer_id,
        )
    except DomainError as exc:
        raise _app(exc) from exc

    from_state = g.state
    if transition == "approve" and suggested_price_minor is not None:
        g.suggested_price_minor = suggested_price_minor
    if transition == "set_price":
        if price_minor is None or price_minor < 0:
            raise AppError("INVALID_PRICE", "priceMinor must be >= 0", 400)
        g.base_price_minor = price_minor
        enqueue(
            db,
            "game.price_changed",
            {"gameId": g.id, "priceMinor": g.base_price_minor},
            producer="catalog",
        )
    if transition == "publish":
        if g.base_price_minor is None:
            raise AppError("PRICE_REQUIRED", "Game has no price set", 400)
        enqueue(
            db,
            "game.published",
            {
                "gameId": g.id,
                "developerId": g.developer_id,
                "title": g.title,
                "priceMinor": g.base_price_minor,
            },
            producer="catalog",
        )

    g.state = new_state.value
    g.updated_at = datetime.now(timezone.utc)
    _history(db, g, from_state, new_state.value, actor_id, note)
    _refresh_search(db, g.id)
    db.commit()
    return _game_dict(db.get(GameRow, game_id))


def start_review(db, game_id, actor_id, roles):
    return _transition(db, game_id, "start_review", actor_id, roles)


def reject(db, game_id, actor_id, roles, note: str | None):
    return _transition(db, game_id, "reject", actor_id, roles, note=note)


def approve(db, game_id, actor_id, roles, suggested_price_minor: int, note: str | None):
    return _transition(
        db,
        game_id,
        "approve",
        actor_id,
        roles,
        note=note,
        suggested_price_minor=suggested_price_minor,
    )


def set_price(db, game_id, actor_id, roles, price_minor: int):
    return _transition(
        db, game_id, "set_price", actor_id, roles, price_minor=price_minor
    )


def publish(db, game_id, actor_id, roles):
    return _transition(db, game_id, "publish", actor_id, roles)


def resubmit(db, game_id, actor_id, roles):
    return _transition(db, game_id, "resubmit", actor_id, roles)


def effective_price(db: Session, game_id: str) -> dict:
    g = db.get(GameRow, game_id)
    if not g:
        raise AppError("GAME_NOT_FOUND", "Game not found", 404)
    published = g.state == GameState.PUBLISHED.value
    base = g.base_price_minor if g.base_price_minor is not None else 0
    discount = 0
    festival_id = None
    now = datetime.now(timezone.utc)
    row = db.get(ActiveDiscountRow, game_id)
    if row and row.starts_at <= now <= row.ends_at:
        discount = row.discount_percent
        festival_id = row.festival_id
    effective = apply_discount(base, discount) if published else base
    return {
        "gameId": g.id,
        "basePriceMinor": base,
        "discountPercent": discount if published else 0,
        "effectivePriceMinor": effective if published else base,
        "festivalId": festival_id if published and discount else None,
        "isPublished": published,
    }


def summary(db: Session, game_id: str) -> dict:
    g = db.get(GameRow, game_id)
    if not g:
        raise AppError("GAME_NOT_FOUND", "Game not found", 404)
    return {
        "gameId": g.id,
        "developerId": g.developer_id,
        "title": g.title,
        "state": g.state,
    }


def upsert_discount(
    db: Session,
    game_id: str,
    festival_id: str,
    discount_percent: int,
    starts_at: str,
    ends_at: str,
) -> None:
    starts = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
    ends = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
    existing = db.get(ActiveDiscountRow, game_id)
    if existing:
        existing.festival_id = festival_id
        existing.discount_percent = discount_percent
        existing.starts_at = starts
        existing.ends_at = ends
    else:
        db.add(
            ActiveDiscountRow(
                game_id=game_id,
                festival_id=festival_id,
                discount_percent=discount_percent,
                starts_at=starts,
                ends_at=ends,
            )
        )


def delete_discounts_for(db: Session, festival_id: str) -> None:
    db.execute(
        delete(ActiveDiscountRow).where(ActiveDiscountRow.festival_id == festival_id)
    )
