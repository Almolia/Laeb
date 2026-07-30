from dataclasses import dataclass

from app.domain.orders import status_for


@dataclass(frozen=True)
class SellCompensation:
    quantity: int
    filled: int
    status: str


def compensate_failed_sell(
    *, quantity: int, filled: int, failed_quantity: int
) -> SellCompensation:
    """Cancel only the failed matched slice while keeping other slices intact.

    Reducing both ``quantity`` and ``filled`` by the failed amount preserves the
    pre-match open remainder. A fully failed order is marked CANCELLED because
    the schema intentionally does not allow zero-quantity orders.
    """
    if failed_quantity <= 0 or failed_quantity > filled:
        raise ValueError("failed quantity must be positive and no greater than filled")
    new_filled = filled - failed_quantity
    new_quantity = quantity - failed_quantity
    if new_quantity == 0:
        return SellCompensation(quantity=quantity, filled=0, status="CANCELLED")
    return SellCompensation(
        quantity=new_quantity,
        filled=new_filled,
        status=status_for(new_quantity, new_filled),
    )
