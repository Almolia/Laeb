import pytest

from app.domain.grants import build_allocations


CANDIDATES = ["u1", "u2", "u3", "u4"]


def test_explicit_recipients_fixed_quantity():
    allocations = build_allocations(
        recipient_mode="EXPLICIT",
        candidate_user_ids=CANDIDATES,
        explicit_user_ids=["u1", "u3"],
        user_count=None,
        quantity_mode="FIXED",
        quantity=3,
        min_quantity=None,
        max_quantity=None,
    )
    assert [(a.user_id, a.quantity) for a in allocations] == [("u1", 3), ("u3", 3)]


def test_explicit_recipients_random_quantity_is_reproducible():
    args = dict(
        recipient_mode="EXPLICIT",
        candidate_user_ids=CANDIDATES,
        explicit_user_ids=["u1", "u2"],
        user_count=None,
        quantity_mode="RANDOM",
        quantity=None,
        min_quantity=1,
        max_quantity=5,
        seed=7,
    )
    assert build_allocations(**args) == build_allocations(**args)


def test_random_recipients_fixed_quantity():
    allocations = build_allocations(
        recipient_mode="RANDOM",
        candidate_user_ids=CANDIDATES,
        explicit_user_ids=None,
        user_count=2,
        quantity_mode="FIXED",
        quantity=4,
        min_quantity=None,
        max_quantity=None,
        seed=1,
    )
    assert len(allocations) == 2
    assert len({a.user_id for a in allocations}) == 2
    assert all(a.quantity == 4 for a in allocations)


def test_random_recipients_random_quantity():
    allocations = build_allocations(
        recipient_mode="RANDOM",
        candidate_user_ids=CANDIDATES,
        explicit_user_ids=None,
        user_count=3,
        quantity_mode="RANDOM",
        quantity=None,
        min_quantity=2,
        max_quantity=6,
        seed=10,
    )
    assert len(allocations) == 3
    assert all(2 <= a.quantity <= 6 for a in allocations)


def test_unknown_explicit_user_is_rejected():
    with pytest.raises(ValueError, match="Unknown userIds"):
        build_allocations(
            recipient_mode="EXPLICIT",
            candidate_user_ids=CANDIDATES,
            explicit_user_ids=["missing"],
            user_count=None,
            quantity_mode="FIXED",
            quantity=1,
            min_quantity=None,
            max_quantity=None,
        )
