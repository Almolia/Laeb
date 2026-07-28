from dataclasses import dataclass
from enum import StrEnum

DEVELOPER_SHARE_PERCENT = 70


class Direction(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class Entry:
    account_id: str
    direction: Direction
    amount_minor: int

    def __post_init__(self) -> None:
        if self.amount_minor < 0:
            raise DomainError("NEGATIVE_AMOUNT", "Amount must not be negative")

    def signed(self) -> int:
        return self.amount_minor if self.direction is Direction.CREDIT else -self.amount_minor


def assert_balanced(entries: list[Entry]) -> None:
    total = sum(entry.signed() for entry in entries)
    if total != 0:
        raise DomainError(
            "LEDGER_UNBALANCED",
            f"Transaction group does not sum to zero (got {total})",
            500,
        )


def split_revenue(amount_minor: int) -> tuple[int, int]:
    if amount_minor < 0:
        raise DomainError("NEGATIVE_AMOUNT", "Amount must not be negative")
    developer = amount_minor * DEVELOPER_SHARE_PERCENT // 100
    platform = amount_minor - developer
    return developer, platform


def purchase_entries(
    buyer_account: str,
    developer_account: str,
    platform_account: str,
    amount_minor: int,
) -> list[Entry]:
    developer, platform = split_revenue(amount_minor)
    entries = [
        Entry(buyer_account, Direction.DEBIT, amount_minor),
        Entry(developer_account, Direction.CREDIT, developer),
        Entry(platform_account, Direction.CREDIT, platform),
    ]
    assert_balanced(entries)
    return entries


def transfer_entries(from_account: str, to_account: str, amount_minor: int) -> list[Entry]:
    if amount_minor < 0:
        raise DomainError("NEGATIVE_AMOUNT", "Amount must not be negative")
    entries = [
        Entry(from_account, Direction.DEBIT, amount_minor),
        Entry(to_account, Direction.CREDIT, amount_minor),
    ]
    assert_balanced(entries)
    return entries


def reverse(entries: list[Entry]) -> list[Entry]:
    flip = {Direction.DEBIT: Direction.CREDIT, Direction.CREDIT: Direction.DEBIT}
    reversed_entries = [
        Entry(entry.account_id, flip[entry.direction], entry.amount_minor)
        for entry in entries
    ]
    assert_balanced(reversed_entries)
    return reversed_entries


def ensure_sufficient(balance_minor: int, amount_minor: int) -> None:
    if amount_minor < 0:
        raise DomainError("NEGATIVE_AMOUNT", "Amount must not be negative")
    if balance_minor < amount_minor:
        raise DomainError(
            "INSUFFICIENT_FUNDS",
            f"Balance {balance_minor} is less than {amount_minor}",
            409,
        )
