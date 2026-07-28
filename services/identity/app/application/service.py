import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.model import DomainError, RequestStatus, Role, RoleRequest, User
from app.infrastructure.models import RoleRequestRow, UserRoleRow, UserRow
from app.infrastructure.security import hash_password, verify_password
from shared_kernel.auth import issue_token
from shared_kernel.errors import AppError
from shared_kernel.outbox import enqueue


def _to_app_error(exc: DomainError) -> AppError:
    return AppError(exc.code, exc.message, exc.status)


def _roles_of(row: UserRow) -> list[str]:
    return [r.role for r in row.roles]


def _load_user(db: Session, user_id: str) -> UserRow:
    row = db.execute(
        select(UserRow)
        .where(UserRow.id == user_id)
        .options(selectinload(UserRow.roles))
    ).scalar_one_or_none()
    if not row:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    return row


def register(
    db: Session, username: str, email: str, password: str
) -> dict:
    user_id = str(uuid.uuid4())
    row = UserRow(
        id=user_id,
        username=username,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(row)
    db.add(
        UserRoleRow(user_id=user_id, role=Role.BASE_USER.value, granted_by=None)
    )
    enqueue(
        db,
        "user.registered",
        {"userId": user_id, "username": username, "email": email},
        producer="identity",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(UserRow).where(
                (UserRow.username == username) | (UserRow.email == email)
            )
        ).scalar_one_or_none()
        if existing and existing.username == username:
            raise AppError("USERNAME_TAKEN", "Username is already taken", 409)
        raise AppError("EMAIL_TAKEN", "Email is already taken", 409)

    db.refresh(row)
    row = _load_user(db, user_id)
    return {
        "userId": row.id,
        "username": row.username,
        "email": row.email,
        "roles": _roles_of(row),
    }


def login(db: Session, username: str, password: str) -> dict:
    row = db.execute(
        select(UserRow)
        .where(UserRow.username == username)
        .options(selectinload(UserRow.roles))
    ).scalar_one_or_none()
    if not row or not verify_password(password, row.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Invalid username or password", 401)
    roles = _roles_of(row)
    token, expires = issue_token(row.id, row.username, roles)
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresIn": expires,
        "userId": row.id,
        "roles": roles,
    }


def me(db: Session, user_id: str) -> dict:
    row = _load_user(db, user_id)
    return {
        "userId": row.id,
        "username": row.username,
        "email": row.email,
        "roles": _roles_of(row),
    }


def create_role_request(db: Session, user_id: str, role: str) -> dict:
    try:
        req = RoleRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            requested_role=Role(role),
        )
    except DomainError as exc:
        raise _to_app_error(exc) from exc
    except ValueError as exc:
        raise AppError("INVALID_ROLE", f"Unknown role: {role}", 400) from exc

    db.add(
        RoleRequestRow(
            id=req.id,
            user_id=req.user_id,
            requested_role=req.requested_role.value,
            status=req.status.value,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            "PENDING_REQUEST_EXISTS",
            "A pending request for this role already exists",
            409,
        )
    return {"requestId": req.id, "status": req.status.value}


def list_my_role_requests(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.execute(
            select(RoleRequestRow)
            .where(RoleRequestRow.user_id == user_id)
            .order_by(RoleRequestRow.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_request_dict(r) for r in rows]


def list_role_requests(db: Session, status: str | None = None) -> list[dict]:
    q = select(RoleRequestRow).order_by(RoleRequestRow.created_at.desc())
    if status:
        q = q.where(RoleRequestRow.status == status)
    rows = db.execute(q).scalars().all()
    return [_request_dict(r) for r in rows]


def _request_dict(r: RoleRequestRow) -> dict:
    return {
        "requestId": r.id,
        "userId": r.user_id,
        "role": r.requested_role,
        "status": r.status,
        "decidedBy": r.decided_by,
        "decidedAt": r.decided_at.isoformat() if r.decided_at else None,
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }


def _decide_request(
    db: Session, request_id: str, admin_id: str, approve: bool
) -> dict:
    row = db.get(RoleRequestRow, request_id)
    if not row:
        raise AppError("REQUEST_NOT_FOUND", "Role request not found", 404)
    domain = RoleRequest(
        id=row.id,
        user_id=row.user_id,
        requested_role=Role(row.requested_role),
        status=RequestStatus(row.status),
        decided_by=row.decided_by,
        decided_at=row.decided_at,
    )
    try:
        if approve:
            domain.approve(admin_id)
        else:
            domain.reject(admin_id)
    except DomainError as exc:
        raise _to_app_error(exc) from exc

    row.status = domain.status.value
    row.decided_by = domain.decided_by
    row.decided_at = domain.decided_at

    if approve:
        user = _load_user(db, row.user_id)
        domain_user = User(
            id=user.id,
            username=user.username,
            email=user.email,
            roles={Role(r) for r in _roles_of(user)},
        )
        try:
            domain_user.grant(Role(row.requested_role))
        except DomainError as exc:
            raise _to_app_error(exc) from exc
        db.add(
            UserRoleRow(
                user_id=user.id,
                role=row.requested_role,
                granted_by=admin_id,
            )
        )
        enqueue(
            db,
            "user.role_granted",
            {
                "userId": user.id,
                "role": row.requested_role,
                "grantedBy": admin_id,
            },
            producer="identity",
        )
        db.commit()
        return {
            "requestId": row.id,
            "status": row.status,
            "userId": user.id,
            "role": row.requested_role,
        }

    db.commit()
    return {"requestId": row.id, "status": row.status}


def approve_role_request(db: Session, request_id: str, admin_id: str) -> dict:
    return _decide_request(db, request_id, admin_id, approve=True)


def reject_role_request(db: Session, request_id: str, admin_id: str) -> dict:
    return _decide_request(db, request_id, admin_id, approve=False)


def grant_role(db: Session, user_id: str, role: str, admin_id: str) -> dict:
    try:
        role_enum = Role(role)
    except ValueError as exc:
        raise AppError("INVALID_ROLE", f"Unknown role: {role}", 400) from exc

    user = _load_user(db, user_id)
    domain_user = User(
        id=user.id,
        username=user.username,
        email=user.email,
        roles={Role(r) for r in _roles_of(user)},
    )
    try:
        domain_user.grant(role_enum)
    except DomainError as exc:
        raise _to_app_error(exc) from exc

    db.add(
        UserRoleRow(user_id=user.id, role=role_enum.value, granted_by=admin_id)
    )
    enqueue(
        db,
        "user.role_granted",
        {"userId": user.id, "role": role_enum.value, "grantedBy": admin_id},
        producer="identity",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("ROLE_ALREADY_GRANTED", f"User already has {role}", 409)
    user = _load_user(db, user_id)
    return {"userId": user.id, "roles": _roles_of(user)}


def revoke_role(db: Session, user_id: str, role: str, admin_id: str) -> dict:
    try:
        role_enum = Role(role)
    except ValueError as exc:
        raise AppError("INVALID_ROLE", f"Unknown role: {role}", 400) from exc

    user = _load_user(db, user_id)
    domain_user = User(
        id=user.id,
        username=user.username,
        email=user.email,
        roles={Role(r) for r in _roles_of(user)},
    )
    try:
        domain_user.revoke(role_enum)
    except DomainError as exc:
        raise _to_app_error(exc) from exc

    row = db.execute(
        select(UserRoleRow).where(
            UserRoleRow.user_id == user_id, UserRoleRow.role == role_enum.value
        )
    ).scalar_one_or_none()
    if row:
        db.delete(row)
    db.commit()
    user = _load_user(db, user_id)
    return {"userId": user.id, "roles": _roles_of(user)}


def get_user(db: Session, user_id: str) -> dict:
    row = _load_user(db, user_id)
    return {
        "userId": row.id,
        "username": row.username,
        "roles": _roles_of(row),
    }


def get_users_by_ids(db: Session, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    rows = (
        db.execute(select(UserRow).where(UserRow.id.in_(ids))).scalars().all()
    )
    return [{"userId": r.id, "username": r.username} for r in rows]
