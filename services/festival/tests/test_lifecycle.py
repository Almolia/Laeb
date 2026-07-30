from datetime import datetime, timedelta, timezone

import pytest

from app.domain.lifecycle import started_payload, validate_window


def test_festival_window_requires_end_after_start():
    start = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        validate_window(start, start)


def test_started_payload_contains_only_passed_approved_entries():
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    payload = started_payload(
        festival_id="f1",
        starts_at=start,
        ends_at=end,
        approved_entries=[("g1", 30), ("g2", 100)],
    )
    assert payload["festivalId"] == "f1"
    assert payload["entries"] == [
        {"gameId": "g1", "discountPercent": 30},
        {"gameId": "g2", "discountPercent": 100},
    ]


def test_one_hundred_percent_discount_is_allowed_in_payload():
    start = datetime.now(timezone.utc)
    payload = started_payload(
        festival_id="f1",
        starts_at=start,
        ends_at=start + timedelta(minutes=1),
        approved_entries=[("g1", 100)],
    )
    assert payload["entries"][0]["discountPercent"] == 100
