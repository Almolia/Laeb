from __future__ import annotations

import os

import httpx

from shared_kernel.errors import AppError

CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog:8000/api/v1/catalog")


def get_game_summary(
    game_id: str, authorization: str, correlation_id: str | None = None
) -> dict:
    headers = {"Authorization": authorization}
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    try:
        response = httpx.get(
            f"{CATALOG_URL}/games/internal/{game_id}/summary",
            headers=headers,
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AppError("CATALOG_UNAVAILABLE", "Catalog service is unavailable", 503) from exc
    try:
        body = response.json()
    except ValueError:
        body = None
    if response.is_success and isinstance(body, dict):
        return body
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error = body["error"]
        raise AppError(
            error.get("code", "CATALOG_ERROR"),
            error.get("message", "Catalog request failed"),
            response.status_code,
        )
    raise AppError("CATALOG_UNAVAILABLE", "Catalog returned an invalid response", 502)
