from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application import service as svc
from shared_kernel.auth import ROLE_DEVELOPER, CurrentUser, get_current_user, requires_role
from shared_kernel.db import get_session

router = APIRouter(prefix="/api/v1/trading", tags=["trading"])


class CreateItemBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    iconUrl: str | None = Field(default=None, max_length=500)


class GrantItemBody(BaseModel):
    recipientMode: str
    userIds: list[str] | None = None
    userCount: int | None = Field(default=None, ge=1)
    quantityMode: str
    quantity: int | None = Field(default=None, ge=1)
    minQuantity: int | None = Field(default=None, ge=1)
    maxQuantity: int | None = Field(default=None, ge=1)
    seed: int | None = None


def _request_context(request: Request) -> tuple[str, str | None]:
    return (
        request.headers.get("Authorization", ""),
        request.headers.get("X-Correlation-Id"),
    )


@router.post("/games/{game_id}/items", status_code=201)
def create_item(
    game_id: str,
    body: CreateItemBody,
    request: Request,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    authorization, correlation_id = _request_context(request)
    return svc.create_item(
        db,
        developer_id=user.user_id,
        game_id=game_id,
        name=body.name,
        description=body.description,
        icon_url=body.iconUrl,
        authorization=authorization,
        correlation_id=correlation_id,
    )


@router.get("/games/{game_id}/items")
def list_items(game_id: str, db: Session = Depends(get_session)):
    return svc.list_game_items(db, game_id)


@router.get("/items/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_session)):
    return svc.get_item(db, item_id)


@router.post("/items/{item_id}/grants")
def grant_item(
    item_id: str,
    body: GrantItemBody,
    request: Request,
    user: CurrentUser = Depends(requires_role(ROLE_DEVELOPER)),
    db: Session = Depends(get_session),
):
    authorization, correlation_id = _request_context(request)
    return svc.grant_item(
        db,
        item_id=item_id,
        developer_id=user.user_id,
        authorization=authorization,
        correlation_id=correlation_id,
        recipient_mode=body.recipientMode,
        user_ids=body.userIds,
        user_count=body.userCount,
        quantity_mode=body.quantityMode,
        quantity=body.quantity,
        min_quantity=body.minQuantity,
        max_quantity=body.maxQuantity,
        seed=body.seed,
    )


@router.get("/inventory/me")
def my_inventory(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.inventory(db, user.user_id)


@router.get("/inventory/{user_id}")
def user_inventory(
    user_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.inventory(db, user_id)
