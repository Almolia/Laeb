import hashlib
import json
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import IdempotencyKey
from shared_kernel.errors import AppError


def _request_hash(scope: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"scope": scope, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def execute_idempotent(
    session: Session,
    key: str | None,
    scope: str,
    payload: dict[str, Any],
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    if not key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required", 400)
    if len(key) > 128:
        raise AppError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key is too long", 400)

    digest = _request_hash(scope, payload)
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(lock_id)))

    existing = session.get(IdempotencyKey, key)
    if existing is not None:
        if existing.request_hash != digest:
            raise AppError(
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency-Key was already used with a different request",
                409,
            )
        return existing.response

    response = operation()
    session.add(IdempotencyKey(key=key, request_hash=digest, response=response))
    session.flush()
    return response
