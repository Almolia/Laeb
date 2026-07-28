import uuid
from collections.abc import Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.model import (
    Direction,
    Entry,
    assert_balanced,
    ensure_sufficient,
    purchase_entries,
    reverse,
    transfer_entries,
)
from app.infrastructure.models import Account, LedgerEntry
from shared_kernel.config import settings
from shared_kernel.errors import AppError
from shared_kernel.logging import correlation_id

Owner = tuple[str, uuid.UUID]


def _platform_owner() -> Owner:
    return "PLATFORM", uuid.UUID(settings.platform_account_id)


def ensure_platform_account(session: Session) -> None:
    """Seed the platform counterparty once migrations are complete."""
    lock_owner_accounts(session, [_platform_owner()])


def lock_owner_accounts(session: Session, owners: Iterable[Owner]) -> dict[Owner, Account]:
    unique_owners = sorted(set(owners), key=lambda item: (item[0], str(item[1])))
    if not unique_owners:
        return {}
    session.execute(
        insert(Account)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "balance_minor": 0,
                }
                for owner_type, owner_id in unique_owners
            ]
        )
        .on_conflict_do_nothing(index_elements=["owner_type", "owner_id"])
    )
    accounts = session.execute(
        select(Account)
        .where(tuple_(Account.owner_type, Account.owner_id).in_(unique_owners))
        .order_by(Account.id)
        .with_for_update()
    ).scalars().all()
    return {(account.owner_type, account.owner_id): account for account in accounts}


def get_user_account(session: Session, user_id: uuid.UUID, lock: bool = False) -> Account:
    if lock:
        return lock_owner_accounts(session, [("USER", user_id)])[("USER", user_id)]
    session.execute(
        insert(Account)
        .values(id=uuid.uuid4(), owner_type="USER", owner_id=user_id, balance_minor=0)
        .on_conflict_do_nothing(index_elements=["owner_type", "owner_id"])
    )
    return session.execute(
        select(Account).where(Account.owner_type == "USER", Account.owner_id == user_id)
    ).scalar_one()


def persist_entries(
    session: Session,
    entries: list[Entry],
    locked_accounts: dict[uuid.UUID, Account],
    *,
    tx_group_id: uuid.UUID,
    reason: str,
    ref_type: str | None,
    ref_id: str | None,
) -> None:
    assert_balanced(entries)
    for entry in entries:
        account_id = uuid.UUID(entry.account_id)
        account = locked_accounts[account_id]
        account.balance_minor += entry.signed()
        session.add(
            LedgerEntry(
                tx_group_id=tx_group_id,
                account_id=account_id,
                direction=entry.direction.value,
                amount_minor=entry.amount_minor,
                reason=reason,
                ref_type=ref_type,
                ref_id=ref_id,
                correlation_id=correlation_id.get(),
            )
        )
    session.flush()


def purchase_split(
    session: Session,
    buyer_id: uuid.UUID,
    developer_id: uuid.UUID,
    amount_minor: int,
    order_id: str,
) -> dict:
    owners = [("USER", buyer_id), ("USER", developer_id), _platform_owner()]
    accounts = lock_owner_accounts(session, owners)
    buyer = accounts[("USER", buyer_id)]
    developer = accounts[("USER", developer_id)]
    platform = accounts[_platform_owner()]
    ensure_sufficient(buyer.balance_minor, amount_minor)
    entries = purchase_entries(
        str(buyer.id), str(developer.id), str(platform.id), amount_minor
    )
    tx_group_id = uuid.uuid4()
    persist_entries(
        session,
        entries,
        {account.id: account for account in accounts.values()},
        tx_group_id=tx_group_id,
        reason="PURCHASE",
        ref_type="ORDER",
        ref_id=order_id,
    )
    return {"txGroupId": str(tx_group_id), "buyerBalanceMinor": buyer.balance_minor}


def credit_user(
    session: Session,
    user_id: uuid.UUID,
    amount_minor: int,
    reason: str,
    ref_type: str | None,
    ref_id: str | None,
) -> dict:
    accounts = lock_owner_accounts(session, [("USER", user_id), _platform_owner()])
    user = accounts[("USER", user_id)]
    platform = accounts[_platform_owner()]
    entries = transfer_entries(str(platform.id), str(user.id), amount_minor)
    tx_group_id = uuid.uuid4()
    persist_entries(
        session,
        entries,
        {account.id: account for account in accounts.values()},
        tx_group_id=tx_group_id,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return {"txGroupId": str(tx_group_id), "balanceMinor": user.balance_minor}


def debit_user(
    session: Session,
    user_id: uuid.UUID,
    amount_minor: int,
    reason: str,
    ref_type: str | None,
    ref_id: str | None,
) -> dict:
    accounts = lock_owner_accounts(session, [("USER", user_id), _platform_owner()])
    user = accounts[("USER", user_id)]
    platform = accounts[_platform_owner()]
    ensure_sufficient(user.balance_minor, amount_minor)
    entries = transfer_entries(str(user.id), str(platform.id), amount_minor)
    tx_group_id = uuid.uuid4()
    persist_entries(
        session,
        entries,
        {account.id: account for account in accounts.values()},
        tx_group_id=tx_group_id,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return {"txGroupId": str(tx_group_id), "balanceMinor": user.balance_minor}


def transfer_users(
    session: Session,
    from_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
    amount_minor: int,
    reason: str,
    ref_type: str | None,
    ref_id: str | None,
) -> dict:
    accounts = lock_owner_accounts(
        session, [("USER", from_user_id), ("USER", to_user_id)]
    )
    sender = accounts[("USER", from_user_id)]
    recipient = accounts[("USER", to_user_id)]
    ensure_sufficient(sender.balance_minor, amount_minor)
    entries = transfer_entries(str(sender.id), str(recipient.id), amount_minor)
    tx_group_id = uuid.uuid4()
    persist_entries(
        session,
        entries,
        {account.id: account for account in accounts.values()},
        tx_group_id=tx_group_id,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return {"txGroupId": str(tx_group_id)}


def reverse_group(session: Session, original_group_id: uuid.UUID, reason: str) -> dict:
    original = session.execute(
        select(LedgerEntry)
        .where(LedgerEntry.tx_group_id == original_group_id)
        .order_by(LedgerEntry.id)
        .with_for_update()
    ).scalars().all()
    if not original:
        raise AppError("TX_GROUP_NOT_FOUND", "Transaction group was not found", 404)
    already_reversed = session.execute(
        select(LedgerEntry.id).where(
            LedgerEntry.ref_type == "REVERSAL",
            LedgerEntry.ref_id == str(original_group_id),
        )
    ).first()
    if already_reversed:
        raise AppError("ALREADY_REVERSED", "Transaction group was already reversed", 409)

    accounts = session.execute(
        select(Account)
        .where(Account.id.in_({entry.account_id for entry in original}))
        .order_by(Account.id)
        .with_for_update()
    ).scalars().all()
    domain_entries = [
        Entry(str(entry.account_id), Direction(entry.direction), entry.amount_minor)
        for entry in original
    ]
    reversal_id = uuid.uuid4()
    persist_entries(
        session,
        reverse(domain_entries),
        {account.id: account for account in accounts},
        tx_group_id=reversal_id,
        reason=reason,
        ref_type="REVERSAL",
        ref_id=str(original_group_id),
    )
    return {"reversalTxGroupId": str(reversal_id)}
