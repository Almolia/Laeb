import pytest

from app.domain.settlement import compensate_failed_sell


def test_failed_partial_match_preserves_pre_match_open_remainder():
    result = compensate_failed_sell(quantity=5, filled=2, failed_quantity=2)
    assert result.quantity == 3
    assert result.filled == 0
    assert result.status == "OPEN"


def test_failed_slice_preserves_other_matched_slices():
    result = compensate_failed_sell(quantity=5, filled=5, failed_quantity=2)
    assert result.quantity == 3
    assert result.filled == 3
    assert result.status == "FILLED"


def test_fully_failed_sell_is_cancelled():
    result = compensate_failed_sell(quantity=2, filled=2, failed_quantity=2)
    assert result.quantity == 2
    assert result.filled == 0
    assert result.status == "CANCELLED"


def test_invalid_failed_quantity_is_rejected():
    with pytest.raises(ValueError):
        compensate_failed_sell(quantity=2, filled=1, failed_quantity=2)
