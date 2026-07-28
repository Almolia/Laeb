"""Pure domain. No framework imports allowed in this file."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class Role(StrEnum):
    BASE_USER = "BASE_USER"
    DEVELOPER = "DEVELOPER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"


REQUESTABLE_ROLES = {Role.DEVELOPER, Role.SUPPORT}  # US-03: cannot request ADMIN


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


@dataclass
class User:
    id: str
    username: str
    email: str
    roles: set[Role] = field(default_factory=lambda: {Role.BASE_USER})

    def grant(self, role: Role) -> None:
        if role in self.roles:
            raise DomainError("ROLE_ALREADY_GRANTED", f"User already has {role}", 409)
        self.roles.add(role)

    def revoke(self, role: Role) -> None:
        if role is Role.BASE_USER:
            raise DomainError("CANNOT_REVOKE_BASE", "BASE_USER cannot be revoked", 400)
        self.roles.discard(role)


@dataclass
class RoleRequest:
    id: str
    user_id: str
    requested_role: Role
    status: RequestStatus = RequestStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None

    def __post_init__(self):
        if self.requested_role not in REQUESTABLE_ROLES:
            raise DomainError(
                "ROLE_NOT_REQUESTABLE",
                "Only DEVELOPER and SUPPORT can be requested",
                400,
            )

    def _decide(self, status: RequestStatus, admin_id: str) -> None:
        if self.status is not RequestStatus.PENDING:
            raise DomainError(
                "REQUEST_ALREADY_DECIDED",
                f"Request is already {self.status}",
                409,
            )
        self.status = status
        self.decided_by = admin_id
        self.decided_at = datetime.now(timezone.utc)

    def approve(self, admin_id: str) -> None:
        self._decide(RequestStatus.APPROVED, admin_id)

    def reject(self, admin_id: str) -> None:
        self._decide(RequestStatus.REJECTED, admin_id)
