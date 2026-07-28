"""All money in this system is an INTEGER number of minor units (e.g. rial/cents).
There is no float anywhere. Ever."""

DEVELOPER_SHARE_PERCENT = 70
GIFT_MESSAGE_SURCHARGE_PER_MILLE = 2  # 0.2% == 2 per 1000


def split_revenue(amount_minor: int) -> tuple[int, int]:
    """70/30 split that always sums back to exactly amount_minor (no lost units)."""
    developer = amount_minor * DEVELOPER_SHARE_PERCENT // 100
    platform = amount_minor - developer
    return developer, platform


def gift_message_surcharge(price_minor: int) -> int:
    """0.2% of the game price, rounded half up."""
    return (price_minor * GIFT_MESSAGE_SURCHARGE_PER_MILLE + 500) // 1000


def apply_discount(price_minor: int, discount_percent: int) -> int:
    """discount_percent is 0..100; 100 means free."""
    if not 0 <= discount_percent <= 100:
        raise ValueError("discount_percent must be between 0 and 100")
    return price_minor - (price_minor * discount_percent // 100)
