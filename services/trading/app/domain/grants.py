"""Pure selection rules for item grants."""

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class GrantAllocation:
    user_id: str
    quantity: int


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def build_allocations(
    *,
    recipient_mode: str,
    candidate_user_ids: list[str],
    explicit_user_ids: list[str] | None,
    user_count: int | None,
    quantity_mode: str,
    quantity: int | None,
    min_quantity: int | None,
    max_quantity: int | None,
    seed: int | None = None,
) -> list[GrantAllocation]:
    """Return deterministic allocations when ``seed`` is supplied.

    Supports all combinations of EXPLICIT/RANDOM recipients and FIXED/RANDOM
    quantities. Validation errors are raised as ``ValueError`` so HTTP and
    persistence concerns stay outside the domain module.
    """

    rng = random.Random(seed)
    recipient_mode = recipient_mode.upper()
    quantity_mode = quantity_mode.upper()
    candidates = _unique(candidate_user_ids)

    if recipient_mode == "EXPLICIT":
        recipients = _unique(explicit_user_ids or [])
        if not recipients:
            raise ValueError("userIds is required for EXPLICIT recipient mode")
        missing = sorted(set(recipients) - set(candidates))
        if missing:
            raise ValueError(f"Unknown userIds: {', '.join(missing)}")
    elif recipient_mode == "RANDOM":
        if user_count is None or user_count <= 0:
            raise ValueError("userCount must be greater than zero for RANDOM mode")
        if user_count > len(candidates):
            raise ValueError("userCount exceeds the number of candidate users")
        recipients = rng.sample(candidates, user_count)
    else:
        raise ValueError("recipientMode must be EXPLICIT or RANDOM")

    if quantity_mode == "FIXED":
        if quantity is None or quantity <= 0:
            raise ValueError("quantity must be greater than zero for FIXED mode")
        quantities = [quantity] * len(recipients)
    elif quantity_mode == "RANDOM":
        if min_quantity is None or max_quantity is None:
            raise ValueError("minQuantity and maxQuantity are required for RANDOM mode")
        if min_quantity <= 0 or max_quantity < min_quantity:
            raise ValueError("quantity range must satisfy 0 < minQuantity <= maxQuantity")
        quantities = [rng.randint(min_quantity, max_quantity) for _ in recipients]
    else:
        raise ValueError("quantityMode must be FIXED or RANDOM")

    return [
        GrantAllocation(user_id=user_id, quantity=amount)
        for user_id, amount in zip(recipients, quantities, strict=True)
    ]
