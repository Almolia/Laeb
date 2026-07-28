from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Request
from pydantic import BaseModel

from .config import settings
from .errors import AppError

ROLE_BASE_USER = "BASE_USER"
ROLE_DEVELOPER = "DEVELOPER"
ROLE_SUPPORT = "SUPPORT"
ROLE_ADMIN = "ADMIN"
ALL_ROLES = [ROLE_BASE_USER, ROLE_DEVELOPER, ROLE_SUPPORT, ROLE_ADMIN]


class CurrentUser(BaseModel):
    user_id: str
    username: str
    roles: list[str]

    def has(self, *roles: str) -> bool:
        return ROLE_ADMIN in self.roles or any(r in self.roles for r in roles)


def issue_token(user_id: str, username: str, roles: list[str]) -> tuple[str, int]:
    """Only the Identity service calls this."""
    expires = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg), expires


def _decode(token: str) -> CurrentUser:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.ExpiredSignatureError:
        raise AppError("TOKEN_EXPIRED", "Access token has expired", 401)
    except jwt.PyJWTError:
        raise AppError("INVALID_TOKEN", "Access token is invalid", 401)
    return CurrentUser(
        user_id=claims["sub"],
        username=claims["username"],
        roles=claims.get("roles", []),
    )


def get_current_user(request: Request) -> CurrentUser:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AppError("UNAUTHENTICATED", "Missing bearer token", 401)
    return _decode(header[7:])


def optional_user(request: Request) -> CurrentUser | None:
    try:
        return get_current_user(request)
    except AppError:
        return None


def requires_role(*roles: str):
    """Usage:  @router.post(..., dependencies=[Depends(requires_role(ROLE_SUPPORT))])"""

    def dependency(request: Request) -> CurrentUser:
        user = get_current_user(request)
        if not user.has(*roles):
            raise AppError("FORBIDDEN", f"Requires one of: {', '.join(roles)}", 403)
        return user

    return dependency
