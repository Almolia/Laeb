import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration
DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL is not configured", allow_module_level=True)

from app.application.ledger import credit_user, purchase_split  # noqa: E402
from app.infrastructure.models import Account, LedgerEntry  # noqa: E402


def test_concurrent_purchases_cannot_double_spend():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    buyer, first_dev, second_dev = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with factory() as seed:
        credit_user(seed, buyer, 500_000, "TOPUP", "TEST", str(uuid.uuid4()))
        seed.commit()

    results: list[object] = []
    barrier = threading.Barrier(2)

    def purchase(developer: uuid.UUID) -> None:
        with factory() as session:
            barrier.wait()
            try:
                result = purchase_split(session, buyer, developer, 500_000, str(uuid.uuid4()))
                session.commit()
                results.append(result)
            except Exception as exc:  # exactly one thread should fail with insufficient funds
                session.rollback()
                results.append(exc)

    threads = [threading.Thread(target=purchase, args=(first_dev,)), threading.Thread(target=purchase, args=(second_dev,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(results) == 2
    assert sum(isinstance(result, dict) for result in results) == 1

    with factory() as session:
        account = session.execute(
            select(Account).where(Account.owner_type == "USER", Account.owner_id == buyer)
        ).scalar_one()
        assert account.balance_minor == 0
    engine.dispose()
