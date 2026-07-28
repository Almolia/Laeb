import pytest

from app.domain.model import (
    Direction,
    DomainError,
    Entry,
    assert_balanced,
    ensure_sufficient,
    purchase_entries,
    reverse,
    split_revenue,
    transfer_entries,
)


@pytest.mark.parametrize(
    ("amount", "developer", "platform"),
    [(0, 0, 0), (1, 0, 1), (100, 70, 30), (999, 699, 300), (500_000, 350_000, 150_000)],
)
def test_split_sums_exactly(amount, developer, platform):
    assert split_revenue(amount) == (developer, platform)
    assert developer + platform == amount


def test_purchase_and_transfer_are_balanced():
    assert_balanced(purchase_entries("buyer", "developer", "platform", 500_000))
    assert_balanced(transfer_entries("buyer", "seller", 10))


def test_reversal_cancels_original_entries():
    original = purchase_entries("buyer", "developer", "platform", 500_000)
    reversed_entries = reverse(original)
    assert sum(entry.signed() for entry in original + reversed_entries) == 0
    assert reversed_entries[0].direction is Direction.CREDIT


def test_unbalanced_and_negative_amount_are_rejected():
    with pytest.raises(DomainError, match="does not sum"):
        assert_balanced([Entry("account", Direction.DEBIT, 100)])
    with pytest.raises(DomainError) as exc:
        split_revenue(-1)
    assert exc.value.code == "NEGATIVE_AMOUNT"


def test_sufficient_funds_rule():
    ensure_sufficient(100, 100)
    with pytest.raises(DomainError) as exc:
        ensure_sufficient(99, 100)
    assert exc.value.code == "INSUFFICIENT_FUNDS"
