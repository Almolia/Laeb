from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from .config import Settings, get_settings
from .errors import AppError

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    roles: tuple[str, ...]


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("AUTH_REQUIRED", "Bearer token is required", 401)
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except InvalidTokenError as exc:
        raise AppError("INVALID_TOKEN", "Access token is invalid or expired", 401) from exc
    roles = claims.get("roles", [])
    if not isinstance(roles, list):
        raise AppError("INVALID_TOKEN", "Token roles claim must be a list", 401)
    return CurrentUser(
        user_id=str(claims["sub"]),
        username=str(claims.get("username", "")),
        roles=tuple(str(role) for role in roles),
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if "ADMIN" not in user.roles:
        raise AppError("FORBIDDEN", "ADMIN role is required", 403)
    return user
