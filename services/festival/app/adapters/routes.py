from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application import service as svc
from shared_kernel.auth import (
    ROLE_ADMIN,
    ROLE_DEVELOPER,
    ROLE_SUPPORT,
    CurrentUser,
    requires_role,
)
from shared_kernel.db import get_session

router = APIRouter(prefix="/api/v1/festival", tags=["festival"])


class CreateFestivalBody(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    startsAt: datetime
    endsAt: datetime


class AddEntryBody(BaseModel):
    gameId: str
    discountPercent: int = Field(ge=0, le=100)


def _request_context(request: Request) -> tuple[str, str | None]:
    return (
        request.headers.get("Authorization", ""),
        request.headers.get("X-Correlation-Id"),
    )


@router.post("/festivals", status_code=201)
def create_festival(
    body: CreateFestivalBody,
    user: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    return svc.create_festival(
        db,
        name=body.name,
        description=body.description,
        starts_at=body.startsAt,
        ends_at=body.endsAt,
        created_by=user.user_id,
    )


@router.post("/festivals/{festival_id}/entries", status_code=201)
def add_entry(
    festival_id: str,
    body: AddEntryBody,
    request: Request,
    _: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    authorization, correlation_id = _request_context(request)
    return svc.add_entry(
        db,
        festival_id=festival_id,
        game_id=body.gameId,
        discount_percent=body.discountPercent,
        authorization=authorization,
        correlation_id=correlation_id,
    )


@router.get("/festivals")
def list_festivals(status: str | None = None, db: Session = Depends(get_session)):
    return svc.list_festivals(db, status)


@router.get("/festivals/entries/pending")
def pending_entries(
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.pending_entries(db, user.user_id)


@router.post("/festivals/{festival_id}/entries/{game_id}/approve")
def approve_entry(
    festival_id: str,
    game_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.decide_entry(
        db,
        festival_id=festival_id,
        game_id=game_id,
        developer_id=user.user_id,
        approve=True,
    )


@router.post("/festivals/{festival_id}/entries/{game_id}/reject")
def reject_entry(
    festival_id: str,
    game_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.decide_entry(
        db,
        festival_id=festival_id,
        game_id=game_id,
        developer_id=user.user_id,
        approve=False,
    )


@router.get("/festivals/{festival_id}")
def get_festival(festival_id: str, db: Session = Depends(get_session)):
    return svc.get_festival(db, festival_id)


@router.post("/internal/festivals/{festival_id}/activate")
def manual_activate(
    festival_id: str,
    _: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.activate_festival(db, festival_id)
