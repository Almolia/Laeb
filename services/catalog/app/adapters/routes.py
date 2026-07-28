from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application import service as svc
from shared_kernel.auth import (
    ROLE_DEVELOPER,
    ROLE_SUPPORT,
    CurrentUser,
    get_current_user,
    requires_role,
)
from shared_kernel.db import get_session

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


class SubmitGameBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    genre: str | None = None
    mediaUrls: list[str] = Field(default_factory=list)
    executableUrl: str | None = None


class NoteBody(BaseModel):
    note: str | None = None


class ApproveBody(BaseModel):
    suggestedPriceMinor: int = Field(ge=0)
    note: str | None = None


class PriceBody(BaseModel):
    priceMinor: int = Field(ge=0)


@router.post("/games", status_code=201)
def submit_game(
    body: SubmitGameBody,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.submit_game(
        db,
        user.user_id,
        body.title,
        body.description,
        body.genre,
        body.mediaUrls,
        body.executableUrl,
    )


@router.get("/games")
def list_games(
    q: str | None = None,
    genre: str | None = None,
    state: str | None = "Published",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    return svc.list_games(db, q=q, genre=genre, state=state, page=page, size=size)


@router.get("/games/mine")
def my_games(
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.list_mine(db, user.user_id)


@router.get("/games/internal/{game_id}/summary")
def internal_summary(
    game_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.summary(db, game_id)


@router.get("/games/{game_id}")
def get_game(game_id: str, db: Session = Depends(get_session)):
    return svc.get_game(db, game_id)


@router.get("/games/{game_id}/history")
def game_history(
    game_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.history(db, game_id, user.user_id, user.roles)


@router.post("/games/{game_id}/review/start")
def start_review(
    game_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    return svc.start_review(db, game_id, user.user_id, user.roles)


@router.post("/games/{game_id}/review/reject")
def reject(
    game_id: str,
    body: NoteBody,
    user: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    return svc.reject(db, game_id, user.user_id, user.roles, body.note)


@router.post("/games/{game_id}/review/approve")
def approve(
    game_id: str,
    body: ApproveBody,
    user: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    return svc.approve(
        db, game_id, user.user_id, user.roles, body.suggestedPriceMinor, body.note
    )


@router.post("/games/{game_id}/price")
def set_price(
    game_id: str,
    body: PriceBody,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.set_price(db, game_id, user.user_id, user.roles, body.priceMinor)


@router.post("/games/{game_id}/publish")
def publish(
    game_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_SUPPORT)),
    db: Session = Depends(get_session),
):
    return svc.publish(db, game_id, user.user_id, user.roles)


@router.post("/games/{game_id}/resubmit")
def resubmit(
    game_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    return svc.resubmit(db, game_id, user.user_id, user.roles)


@router.get("/games/{game_id}/effective-price")
def effective_price(game_id: str, db: Session = Depends(get_session)):
    return svc.effective_price(db, game_id)
