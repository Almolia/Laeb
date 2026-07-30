from __future__ import annotations

from datetime import datetime, timezone


VALID_STATUSES = {"DRAFT", "ACTIVE", "ENDED"}
VALID_ENTRY_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_window(starts_at: datetime, ends_at: datetime) -> tuple[datetime, datetime]:
    starts = normalize_datetime(starts_at)
    ends = normalize_datetime(ends_at)
    if ends <= starts:
        raise ValueError("endsAt must be later than startsAt")
    return starts, ends


def started_payload(
    *,
    festival_id: str,
    starts_at: datetime,
    ends_at: datetime,
    approved_entries: list[tuple[str, int]],
) -> dict:
    return {
        "festivalId": festival_id,
        "startsAt": normalize_datetime(starts_at).isoformat(),
        "endsAt": normalize_datetime(ends_at).isoformat(),
        "entries": [
            {"gameId": game_id, "discountPercent": discount}
            for game_id, discount in approved_entries
        ],
    }
