import pytest

from app.domain.model import DomainError, Role, RoleRequest, User


def test_cannot_request_admin():
    with pytest.raises(DomainError) as exc:
        RoleRequest(id="1", user_id="u", requested_role=Role.ADMIN)
    assert exc.value.code == "ROLE_NOT_REQUESTABLE"


def test_double_decision_rejected():
    r = RoleRequest(id="1", user_id="u", requested_role=Role.DEVELOPER)
    r.approve("admin")
    with pytest.raises(DomainError) as exc:
        r.reject("admin")
    assert exc.value.code == "REQUEST_ALREADY_DECIDED"


def test_base_user_cannot_be_revoked():
    u = User(id="1", username="a", email="a@b.c")
    with pytest.raises(DomainError) as exc:
        u.revoke(Role.BASE_USER)
    assert exc.value.code == "CANNOT_REVOKE_BASE"


def test_grant_duplicate_role():
    u = User(id="1", username="a", email="a@b.c")
    u.grant(Role.DEVELOPER)
    with pytest.raises(DomainError) as exc:
        u.grant(Role.DEVELOPER)
    assert exc.value.code == "ROLE_ALREADY_GRANTED"


def test_approve_sets_status():
    r = RoleRequest(id="1", user_id="u", requested_role=Role.SUPPORT)
    r.approve("admin-1")
    assert r.status.value == "APPROVED"
    assert r.decided_by == "admin-1"
    assert r.decided_at is not None
