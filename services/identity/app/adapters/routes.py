from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.application import service as svc
from shared_kernel.auth import (
    ROLE_ADMIN,
    ROLE_BASE_USER,
    CurrentUser,
    get_current_user,
    requires_role,
)
from shared_kernel.db import get_session
from shared_kernel.errors import AppError

router = APIRouter(prefix="/api/v1/identity", tags=["identity"])


class RegisterBody(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginBody(BaseModel):
    username: str
    password: str


class RoleBody(BaseModel):
    role: str


@router.post("/auth/register", status_code=201)
def register(body: RegisterBody, db: Session = Depends(get_session)):
    return svc.register(db, body.username, body.email, body.password)


@router.post("/auth/login")
def login(body: LoginBody, db: Session = Depends(get_session)):
    return svc.login(db, body.username, body.password)


@router.get("/auth/me")
def auth_me(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.me(db, user.user_id)


@router.post("/role-requests", status_code=201)
def create_role_request(
    body: RoleBody,
    user: CurrentUser = Depends(requires_role(ROLE_BASE_USER)),
    db: Session = Depends(get_session),
):
    return svc.create_role_request(db, user.user_id, body.role)


@router.get("/role-requests/me")
def my_role_requests(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.list_my_role_requests(db, user.user_id)


@router.get("/role-requests")
def list_role_requests(
    status: str | None = Query(default=None),
    _: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.list_role_requests(db, status)


@router.post("/role-requests/{request_id}/approve")
def approve_role_request(
    request_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.approve_role_request(db, request_id, user.user_id)


@router.post("/role-requests/{request_id}/reject")
def reject_role_request(
    request_id: str,
    user: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.reject_role_request(db, request_id, user.user_id)


@router.post("/users/{user_id}/roles")
def grant_role(
    user_id: str,
    body: RoleBody,
    user: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.grant_role(db, user_id, body.role, user.user_id)


@router.delete("/users/{user_id}/roles/{role}")
def revoke_role(
    user_id: str,
    role: str,
    user: CurrentUser = Depends(requires_role(ROLE_ADMIN)),
    db: Session = Depends(get_session),
):
    return svc.revoke_role(db, user_id, role, user.user_id)


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    return svc.get_user(db, user_id)


@router.get("/users")
def get_users(
    ids: str | None = Query(default=None, description="Optional comma-separated user ids"),
    _: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    if ids is None:
        return svc.list_users(db)
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if not id_list:
        raise AppError("VALIDATION_ERROR", "ids must contain at least one user id", 422)
    return svc.get_users_by_ids(db, id_list)
