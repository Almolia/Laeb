import pytest

from app.domain.orders import available_items, remaining, status_for


def test_available_items_excludes_reserved_units():
    assert available_items(10, 4) == 6


def test_invalid_reservation_is_rejected():
    with pytest.raises(ValueError):
        available_items(2, 3)


def test_order_status_from_fill():
    assert status_for(5, 0) == "OPEN"
    assert status_for(5, 2) == "PARTIAL"
    assert status_for(5, 5) == "FILLED"


def test_remaining_rejects_overfill():
    with pytest.raises(ValueError):
        remaining(1, 2)
