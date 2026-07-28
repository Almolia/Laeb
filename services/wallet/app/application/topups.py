import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ledger import credit_user
from app.infrastructure.models import Topup
from app.infrastructure.outbox import enqueue
from shared_kernel.config import get_settings
from shared_kernel.errors import AppError


def initiate_topup(session: Session, user_id: uuid.UUID, amount_minor: int) -> dict:
    if amount_minor <= 0:
        raise AppError("INVALID_AMOUNT", "Top-up amount must be greater than zero", 400)
    topup = Topup(user_id=user_id, amount_minor=amount_minor, status="PENDING")
    session.add(topup)
    session.flush()
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.mock_psp_url.rstrip('/')}/charge",
            json={
                "amountMinor": amount_minor,
                "callbackUrl": settings.wallet_callback_url,
                "reference": str(topup.id),
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AppError("PSP_UNAVAILABLE", "Payment provider is unavailable", 502) from exc
    data = response.json()
    topup.psp_payment_id = data["paymentId"]
    topup.redirect_url = data["redirectUrl"]
    return {"topupId": str(topup.id), "redirectUrl": topup.redirect_url}


def handle_callback(
    session: Session,
    payment_id: str,
    reference: str,
    status: str,
) -> dict:
    try:
        topup_id = uuid.UUID(reference)
    except ValueError as exc:
        raise AppError("TOPUP_NOT_FOUND", "Top-up reference is invalid", 404) from exc
    topup = session.execute(
        select(Topup).where(Topup.id == topup_id).with_for_update()
    ).scalar_one_or_none()
    if topup is None:
        raise AppError("TOPUP_NOT_FOUND", "Top-up was not found", 404)
    if topup.psp_payment_id and topup.psp_payment_id != payment_id:
        raise AppError("TOPUP_REFERENCE_MISMATCH", "PSP payment does not match top-up", 409)
    if topup.status == "SUCCEEDED":
        return {"status": "SUCCEEDED", "topupId": str(topup.id), "credited": False}
    if topup.status == "FAILED":
        return {"status": "FAILED", "topupId": str(topup.id), "credited": False}
    if status not in {"SUCCEEDED", "FAILED"}:
        raise AppError("INVALID_TOPUP_STATUS", "Top-up status is invalid", 400)
    topup.status = status
    if status == "FAILED":
        return {"status": "FAILED", "topupId": str(topup.id), "credited": False}

    credit = credit_user(
        session,
        topup.user_id,
        topup.amount_minor,
        reason="TOPUP",
        ref_type="TOPUP",
        ref_id=str(topup.id),
    )
    enqueue(
        session,
        "wallet.topped_up",
        {"userId": str(topup.user_id), "amountMinor": topup.amount_minor, "source": "PSP"},
    )
    return {
        "status": "SUCCEEDED",
        "topupId": str(topup.id),
        "credited": True,
        "newBalanceMinor": credit["balanceMinor"],
    }
