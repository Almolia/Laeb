import uuid

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.idempotency import execute_idempotent
from app.application.giftcards import create_cards, redeem_card
from app.application.ledger import (
    credit_user,
    debit_user,
    get_user_account,
    purchase_split,
    reverse_group,
    transfer_users,
)
from app.application.topups import handle_callback, initiate_topup
from app.infrastructure.models import LedgerEntry
from shared_kernel.auth import ROLE_ADMIN, CurrentUser, get_current_user, requires_role
from shared_kernel.db import get_session
from shared_kernel.errors import AppError

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PurchaseSplitIn(ApiModel):
    buyerId: uuid.UUID
    developerId: uuid.UUID
    amountMinor: int = Field(ge=0)
    orderId: str = Field(min_length=1, max_length=64)


class MoneyOperationIn(ApiModel):
    userId: uuid.UUID
    amountMinor: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=40)
    refType: str | None = Field(default=None, max_length=20)
    refId: str | None = Field(default=None, max_length=64)


class TransferIn(ApiModel):
    fromUserId: uuid.UUID
    toUserId: uuid.UUID
    amountMinor: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=40)
    refType: str | None = Field(default=None, max_length=20)
    refId: str | None = Field(default=None, max_length=64)


class ReverseIn(ApiModel):
    txGroupId: uuid.UUID
    reason: str = Field(min_length=1, max_length=40)


class TopupIn(ApiModel):
    amountMinor: int = Field(gt=0)


class TopupCallbackIn(ApiModel):
    paymentId: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=64)
    status: str


class GiftcardCreateIn(ApiModel):
    amountMinor: int = Field(gt=0)
    count: int = Field(gt=0, le=1000)


class GiftcardRedeemIn(ApiModel):
    code: str = Field(min_length=19, max_length=19)


def _user_uuid(user: CurrentUser) -> uuid.UUID:
    try:
        return uuid.UUID(user.user_id)
    except ValueError as exc:
        raise AppError("INVALID_TOKEN", "Token sub must be a UUID", 401) from exc


@router.get("/wallets/me")
def my_wallet(
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    user_id = _user_uuid(user)
    account = get_user_account(session, user_id)
    session.commit()
    return {"userId": str(user_id), "balanceMinor": account.balance_minor}


@router.get("/wallets/me/ledger")
def my_ledger(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    account = get_user_account(session, _user_uuid(user))
    entries = session.execute(
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account.id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()
    session.commit()
    return [
        {
            "txGroupId": str(entry.tx_group_id),
            "direction": entry.direction,
            "amountMinor": entry.amount_minor,
            "reason": entry.reason,
            "refType": entry.ref_type,
            "refId": entry.ref_id,
            "createdAt": entry.created_at,
        }
        for entry in entries
    ]


@router.post("/topups/initiate")
def topup_initiate(
    body: TopupIn,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    result = initiate_topup(session, _user_uuid(user), body.amountMinor)
    session.commit()
    return result


@router.post("/topups/callback")
def topup_callback(body: TopupCallbackIn, session: Session = Depends(get_session)) -> dict:
    result = handle_callback(session, body.paymentId, body.reference, body.status)
    session.commit()
    return result


@router.post("/giftcards", status_code=201)
def giftcard_create(
    body: GiftcardCreateIn,
    _admin: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    session: Session = Depends(get_session),
) -> dict:
    result = {"codes": create_cards(session, body.amountMinor, body.count)}
    session.commit()
    return result


@router.post("/giftcards/redeem")
def giftcard_redeem(
    body: GiftcardRedeemIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    user_id = _user_uuid(user)
    return execute_idempotent(
        session,
        idempotency_key,
        "giftcard-redeem",
        {"code": body.code.upper(), "userId": str(user_id)},
        lambda: redeem_card(session, user_id, body.code),
    )


@router.post("/internal/purchase-split")
def internal_purchase_split(
    body: PurchaseSplitIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    payload = body.model_dump(mode="json")
    return execute_idempotent(
        session,
        idempotency_key,
        "purchase-split",
        payload,
        lambda: purchase_split(session, **{
            "buyer_id": body.buyerId,
            "developer_id": body.developerId,
            "amount_minor": body.amountMinor,
            "order_id": body.orderId,
        }),
    )


@router.post("/internal/credit")
def internal_credit(
    body: MoneyOperationIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    return execute_idempotent(
        session,
        idempotency_key,
        "credit",
        body.model_dump(mode="json"),
        lambda: credit_user(
            session, body.userId, body.amountMinor, body.reason, body.refType, body.refId
        ),
    )


@router.post("/internal/debit")
def internal_debit(
    body: MoneyOperationIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    return execute_idempotent(
        session,
        idempotency_key,
        "debit",
        body.model_dump(mode="json"),
        lambda: debit_user(
            session, body.userId, body.amountMinor, body.reason, body.refType, body.refId
        ),
    )


@router.post("/internal/transfer")
def internal_transfer(
    body: TransferIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    return execute_idempotent(
        session,
        idempotency_key,
        "transfer",
        body.model_dump(mode="json"),
        lambda: transfer_users(
            session,
            body.fromUserId,
            body.toUserId,
            body.amountMinor,
            body.reason,
            body.refType,
            body.refId,
        ),
    )


@router.post("/internal/reverse")
def internal_reverse(
    body: ReverseIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> dict:
    return execute_idempotent(
        session,
        idempotency_key,
        "reverse",
        body.model_dump(mode="json"),
        lambda: reverse_group(session, body.txGroupId, body.reason),
    )
