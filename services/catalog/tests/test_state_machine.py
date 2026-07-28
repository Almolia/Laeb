import pytest

from app.domain.state_machine import DomainError, GameState, check


def test_happy_path_to_published():
    s = GameState.SUBMITTED
    s = check("start_review", s, ["SUPPORT"], "sup", "dev")
    assert s is GameState.UNDER_REVIEW
    s = check("approve", s, ["SUPPORT"], "sup", "dev")
    assert s is GameState.PRICE_SUGGESTED
    s = check("set_price", s, ["DEVELOPER"], "dev", "dev")
    assert s is GameState.PRICE_PROPOSED
    s = check("publish", s, ["SUPPORT"], "sup", "dev")
    assert s is GameState.PUBLISHED


def test_reject_and_resubmit():
    s = GameState.SUBMITTED
    s = check("start_review", s, ["SUPPORT"], "sup", "dev")
    s = check("reject", s, ["SUPPORT"], "sup", "dev")
    assert s is GameState.REJECTED
    s = check("resubmit", s, ["DEVELOPER"], "dev", "dev")
    assert s is GameState.SUBMITTED


def test_publish_from_submitted_illegal():
    with pytest.raises(DomainError) as exc:
        check("publish", GameState.SUBMITTED, ["SUPPORT"], "sup", "dev")
    assert exc.value.code == "ILLEGAL_TRANSITION"
    assert exc.value.status == 409


def test_set_price_non_owner():
    with pytest.raises(DomainError) as exc:
        check(
            "set_price",
            GameState.PRICE_SUGGESTED,
            ["DEVELOPER"],
            "other-dev",
            "dev",
        )
    assert exc.value.code == "NOT_GAME_OWNER"
    assert exc.value.status == 403


def test_approve_as_base_user_forbidden():
    with pytest.raises(DomainError) as exc:
        check("approve", GameState.UNDER_REVIEW, ["BASE_USER"], "u", "dev")
    assert exc.value.code == "FORBIDDEN"
    assert exc.value.status == 403


def test_double_publish_illegal():
    with pytest.raises(DomainError) as exc:
        check("publish", GameState.PUBLISHED, ["SUPPORT"], "sup", "dev")
    assert exc.value.code == "ILLEGAL_TRANSITION"


def test_admin_can_act_as_support():
    s = check("start_review", GameState.SUBMITTED, ["ADMIN"], "admin", "dev")
    assert s is GameState.UNDER_REVIEW
