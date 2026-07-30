"""Pure domain logic for the five-minute marketplace matching cycle.

This module intentionally has no database, web-framework, messaging, Redis, or
clock dependencies.  The application layer is responsible for loading open
orders, converting them to ``BookOrder`` instances, persisting the returned
matches, and publishing events.
"""

from dataclasses import dataclass


@dataclass
class BookOrder:
    """An open order as seen by the matching engine.

    ``quantity`` is the remaining unfilled quantity.  It is reduced in place as
    matches are produced so the caller can observe any remainder that must stay
    open on the order book.
    """

    id: str
    user_id: str
    price_minor: int
    quantity: int
    created_at: float


@dataclass(frozen=True)
class Match:
    """A proposed trade between one buy order and one sell order."""

    buy_order_id: str
    sell_order_id: str
    buyer_id: str
    seller_id: str
    price_minor: int
    quantity: int


def match_orders(buys: list[BookOrder], sells: list[BookOrder]) -> list[Match]:
    """Match eligible buy and sell orders until no eligible pair remains.

    A pair is eligible when the buy price is greater than or equal to the sell
    price and the two orders belong to different users.  At every round, the
    engine chooses the eligible pair with the smallest ``buy - sell`` price
    difference.  Therefore exact-price matches (difference zero) are naturally
    selected first.  Ties are resolved by the oldest buy and then the oldest
    sell, providing first-come-first-served fairness.

    Every trade settles at the seller's price.  Partial fills are supported and
    remaining quantities stay on the supplied ``BookOrder`` objects.
    """

    active_buys = [order for order in buys if order.quantity > 0]
    active_sells = [order for order in sells if order.quantity > 0]
    matches: list[Match] = []

    while True:
        best: tuple[int, float, float, BookOrder, BookOrder] | None = None

        for buy in active_buys:
            if buy.quantity <= 0:
                continue

            for sell in active_sells:
                if sell.quantity <= 0:
                    continue
                if buy.user_id == sell.user_id:
                    continue
                if buy.price_minor < sell.price_minor:
                    continue

                candidate = (
                    buy.price_minor - sell.price_minor,
                    buy.created_at,
                    sell.created_at,
                    buy,
                    sell,
                )
                if best is None or candidate[:3] < best[:3]:
                    best = candidate

        if best is None:
            return matches

        _, _, _, buy, sell = best
        matched_quantity = min(buy.quantity, sell.quantity)

        matches.append(
            Match(
                buy_order_id=buy.id,
                sell_order_id=sell.id,
                buyer_id=buy.user_id,
                seller_id=sell.user_id,
                price_minor=sell.price_minor,
                quantity=matched_quantity,
            )
        )

        buy.quantity -= matched_quantity
        sell.quantity -= matched_quantity
