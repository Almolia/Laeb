import logging
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.model import Role
from app.infrastructure.models import UserRoleRow, UserRow
from app.infrastructure.security import hash_password
from shared_kernel.db import session_factory
from shared_kernel.outbox import enqueue

log = logging.getLogger(__name__)


def ensure_admin(username: str, password: str) -> None:
    """Idempotent: if username exists, do nothing."""
    factory = session_factory()
    with factory() as db:
        existing = db.execute(
            select(UserRow).where(UserRow.username == username)
        ).scalar_one_or_none()
        if existing:
            log.info("admin account ready")
            return

        admin_id = str(uuid.uuid4())
        db.add(
            UserRow(
                id=admin_id,
                username=username,
                email=f"{username}@laeb.local",
                password_hash=hash_password(password),
            )
        )
        db.add(
            UserRoleRow(
                user_id=admin_id,
                role=Role.ADMIN.value,
                granted_by=None,
            )
        )
        db.add(
            UserRoleRow(
                user_id=admin_id,
                role=Role.BASE_USER.value,
                granted_by=None,
            )
        )
        enqueue(
            db,
            "user.registered",
            {"userId": admin_id, "username": username, "email": f"{username}@laeb.local"},
            producer="identity",
        )
        enqueue(
            db,
            "user.role_granted",
            {"userId": admin_id, "role": Role.ADMIN.value, "grantedBy": admin_id},
            producer="identity",
        )
        db.commit()
        log.info("admin account ready")


def seed_admin_from_env() -> None:
    ensure_admin(
        os.getenv("ADMIN_USERNAME", "admin"),
        os.getenv("ADMIN_PASSWORD", "admin123"),
    )
