from __future__ import annotations

import os

import httpx

from shared_kernel.errors import AppError

CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog:8000/api/v1/catalog")
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity:8000/api/v1/identity")


def _headers(authorization: str, correlation_id: str | None) -> dict[str, str]:
    headers = {"Authorization": authorization}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    return headers


def _json_or_error(response: httpx.Response, dependency: str):
    try:
        body = response.json()
    except ValueError:
        body = None
    if response.is_success:
        return body
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error = body["error"]
        raise AppError(
            error.get("code", f"{dependency.upper()}_ERROR"),
            error.get("message", f"{dependency} request failed"),
            response.status_code,
        )
    raise AppError(
        f"{dependency.upper()}_UNAVAILABLE",
        f"{dependency} request failed with status {response.status_code}",
        502,
    )


def get_game_summary(
    game_id: str, authorization: str, correlation_id: str | None = None
) -> dict:
    try:
        response = httpx.get(
            f"{CATALOG_URL}/games/internal/{game_id}/summary",
            headers=_headers(authorization, correlation_id),
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AppError("CATALOG_UNAVAILABLE", "Catalog service is unavailable", 503) from exc
    return _json_or_error(response, "catalog")


def get_users(
    authorization: str,
    correlation_id: str | None = None,
    user_ids: list[str] | None = None,
) -> list[dict]:
    params = {"ids": ",".join(user_ids)} if user_ids else None
    try:
        response = httpx.get(
            f"{IDENTITY_URL}/users",
            params=params,
            headers=_headers(authorization, correlation_id),
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AppError("IDENTITY_UNAVAILABLE", "Identity service is unavailable", 503) from exc
    body = _json_or_error(response, "identity")
    if not isinstance(body, list):
        raise AppError("IDENTITY_INVALID_RESPONSE", "Identity returned an invalid user list", 502)
    return body
