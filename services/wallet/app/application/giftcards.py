import secrets
import string
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ledger import credit_user
from app.infrastructure.models import GiftCard
from shared_kernel.errors import AppError

ALPHABET = string.ascii_uppercase + string.digits


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(16))
    return "-".join(raw[index : index + 4] for index in range(0, 16, 4))


def create_cards(session: Session, amount_minor: int, count: int) -> list[str]:
    if amount_minor <= 0 or count <= 0 or count > 1000:
        raise AppError("INVALID_GIFTCARD_REQUEST", "Amount and count must be positive; count <= 1000", 400)
    codes: list[str] = []
    while len(codes) < count:
        code = new_code()
        if code in codes or session.get(GiftCard, code):
            continue
        session.add(GiftCard(code=code, amount_minor=amount_minor))
        codes.append(code)
    session.flush()
    return codes


def redeem_card(session: Session, user_id: uuid.UUID, code: str) -> dict:
    card = session.execute(
        select(GiftCard).where(GiftCard.code == code.upper()).with_for_update()
    ).scalar_one_or_none()
    if card is None:
        raise AppError("GIFTCARD_NOT_FOUND", "No such gift card", 404)
    if card.redeemed_by is not None:
        raise AppError("GIFTCARD_ALREADY_REDEEMED", "This gift card was already used", 409)
    from datetime import datetime, timezone

    card.redeemed_by = user_id
    card.redeemed_at = datetime.now(timezone.utc)
    result = credit_user(
        session,
        user_id,
        card.amount_minor,
        reason="GIFTCARD",
        ref_type="GIFTCARD",
        ref_id=card.code,
    )
    return {"amountMinor": card.amount_minor, "newBalanceMinor": result["balanceMinor"]}
