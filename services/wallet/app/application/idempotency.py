from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared_kernel.errors import AppError
from shared_kernel.idempotency import record, replay


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

    # A transaction-scoped advisory lock closes the race left between A1's
    # replay() and record() helpers when two retries arrive concurrently.
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
    scoped_payload = {"operation": scope, "payload": payload}
    existing = replay(session, key, scoped_payload)
    if existing is not None:
        session.commit()
        return existing

    response = operation()
    record(session, key, scoped_payload, response)
    session.commit()
    return response
