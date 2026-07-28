"""PostgreSQL integration tests.

Run with TEST_DATABASE_URL pointing at a database that has ``alembic upgrade head`` applied.
The module is skipped when no integration database is configured, so the domain suite remains
useful on a laptop without Docker.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration
DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL is not configured", allow_module_level=True)

from app.application.idempotency import execute_idempotent  # noqa: E402
from app.application.ledger import credit_user, purchase_split, reverse_group  # noqa: E402
from app.infrastructure.models import Account, LedgerEntry  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db
        db.rollback()
    engine.dispose()


def test_purchase_idempotency_and_ledger_invariant(session):
    buyer, developer = uuid.uuid4(), uuid.uuid4()
    credit_user(session, buyer, 500_000, "TOPUP", "TEST", str(uuid.uuid4()))
    session.commit()
    body = {
        "buyerId": str(buyer),
        "developerId": str(developer),
        "amountMinor": 500_000,
        "orderId": str(uuid.uuid4()),
    }
    key = str(uuid.uuid4())
    first = execute_idempotent(
        session,
        key,
        "purchase-split",
        body,
        lambda: purchase_split(session, buyer, developer, 500_000, body["orderId"]),
    )
    session.commit()
    second = execute_idempotent(
        session,
        key,
        "purchase-split",
        body,
        lambda: pytest.fail("idempotency operation was executed twice"),
    )
    assert first == second
    session.commit()

    rows = session.execute(
        text(
            "SELECT SUM(CASE WHEN direction='CREDIT' THEN amount_minor "
            "ELSE -amount_minor END) FROM ledger_entries WHERE tx_group_id = :id"
        ),
        {"id": uuid.UUID(first["txGroupId"])},
    ).scalar_one()
    assert rows == 0


def test_reversal_restores_balances(session):
    buyer, developer = uuid.uuid4(), uuid.uuid4()
    credit_user(session, buyer, 500_000, "TOPUP", "TEST", str(uuid.uuid4()))
    session.commit()
    result = purchase_split(session, buyer, developer, 500_000, str(uuid.uuid4()))
    session.commit()
    reversal = reverse_group(session, uuid.UUID(result["txGroupId"]), "REFUND")
    session.commit()
    assert reversal["reversalTxGroupId"]
    values = session.execute(
        text(
            "SELECT a.owner_type, a.owner_id, a.balance_minor "
            "FROM accounts a WHERE a.owner_id IN (:buyer, :developer)"
        ),
        {"buyer": buyer, "developer": developer},
    ).all()
    balances = {row.owner_id: row.balance_minor for row in values}
    assert balances[buyer] == 500_000
    assert balances[developer] == 0
