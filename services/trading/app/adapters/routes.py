from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application import service as svc
from app.application.matching_cycle import list_match_cycles, run_cycle_with_lock
from shared_kernel.auth import ROLE_ADMIN, ROLE_DEVELOPER, CurrentUser, get_current_user, requires_role
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


class OrderBody(BaseModel):
    itemId: str
    priceMinor: int = Field(gt=0)
    quantity: int = Field(gt=0)


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



@router.post("/orders/buy", status_code=201)
def buy_order(
    body: OrderBody,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.place_buy_order(
        db,
        user_id=user.user_id,
        item_id=body.itemId,
        price_minor=body.priceMinor,
        quantity=body.quantity,
    )


@router.post("/orders/sell", status_code=201)
def sell_order(
    body: OrderBody,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.place_sell_order(
        db,
        user_id=user.user_id,
        item_id=body.itemId,
        price_minor=body.priceMinor,
        quantity=body.quantity,
    )


@router.get("/orders/me")
def my_orders(
    status: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.list_my_orders(db, user.user_id, status)


@router.delete("/orders/{order_id}")
def cancel_order(
    order_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.cancel_order(db, order_id, user.user_id)


@router.get("/items/{item_id}/orderbook")
def get_orderbook(item_id: str, db: Session = Depends(get_session)):
    return svc.orderbook(db, item_id)


@router.get("/trades")
def get_trades(
    itemId: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.trade_history(db, item_id=itemId, limit=limit)



@router.get("/match-cycles")
def get_match_cycles(
    limit: int = Query(default=20, ge=1, le=100),
    _: CurrentUser = Depends(get_current_user),
):
    return list_match_cycles(limit)


@router.post("/internal/run-match-cycle")
def manual_match_cycle(
    _: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
):
    return run_cycle_with_lock()
