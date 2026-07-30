"""Pure order-book invariants shared by HTTP and settlement code."""

OPEN_STATUSES = {"OPEN", "PARTIAL"}
VALID_STATUSES = OPEN_STATUSES | {"FILLED", "CANCELLED"}
VALID_SIDES = {"BUY", "SELL"}


def remaining(quantity: int, filled: int) -> int:
    value = quantity - filled
    if value < 0:
        raise ValueError("filled quantity cannot exceed order quantity")
    return value


def status_for(quantity: int, filled: int) -> str:
    left = remaining(quantity, filled)
    if left == 0:
        return "FILLED"
    if filled > 0:
        return "PARTIAL"
    return "OPEN"


def available_items(quantity: int, reserved: int) -> int:
    value = quantity - reserved
    if value < 0:
        raise ValueError("reserved quantity cannot exceed holding quantity")
    return value
