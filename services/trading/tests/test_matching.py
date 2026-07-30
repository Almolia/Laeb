from app.domain.matching import BookOrder, match_orders


def order(
    order_id: str,
    user_id: str,
    price_minor: int,
    quantity: int = 1,
    created_at: float = 0.0,
) -> BookOrder:
    return BookOrder(order_id, user_id, price_minor, quantity, created_at)


def test_exact_price_match():
    matches = match_orders(
        [order("b1", "u1", 100)],
        [order("s1", "u2", 100)],
    )

    assert len(matches) == 1
    assert matches[0].price_minor == 100


def test_buyer_pays_sellers_lower_price():
    matches = match_orders(
        [order("b1", "u1", 150)],
        [order("s1", "u2", 100)],
    )

    assert matches[0].price_minor == 100


def test_minimum_difference_wins():
    matches = match_orders(
        [order("b1", "u1", 150)],
        [order("s1", "u2", 100), order("s2", "u3", 140)],
    )

    assert matches[0].sell_order_id == "s2"
    assert matches[0].price_minor == 140


def test_no_match_when_buy_below_sell():
    assert (
        match_orders(
            [order("b1", "u1", 90)],
            [order("s1", "u2", 100)],
        )
        == []
    )


def test_no_self_trade():
    assert (
        match_orders(
            [order("b1", "u1", 100)],
            [order("s1", "u1", 100)],
        )
        == []
    )


def test_partial_fill_leaves_remainder():
    buys = [order("b1", "u1", 100, quantity=5)]
    sells = [order("s1", "u2", 100, quantity=2)]

    matches = match_orders(buys, sells)

    assert len(matches) == 1
    assert matches[0].quantity == 2
    assert buys[0].quantity == 3
    assert sells[0].quantity == 0


def test_oldest_buy_order_wins_a_tie():
    matches = match_orders(
        [
            order("b1", "u1", 100, created_at=1.0),
            order("b2", "u3", 100, created_at=0.0),
        ],
        [order("s1", "u2", 100)],
    )

    assert matches[0].buy_order_id == "b2"


def test_oldest_sell_order_wins_after_buy_tie():
    matches = match_orders(
        [order("b1", "u1", 100, created_at=0.0)],
        [
            order("s1", "u2", 100, created_at=1.0),
            order("s2", "u3", 100, created_at=0.0),
        ],
    )

    assert matches[0].sell_order_id == "s2"


def test_multiple_rounds():
    matches = match_orders(
        [order("b1", "u1", 100), order("b2", "u3", 120)],
        [order("s1", "u2", 90), order("s2", "u4", 110)],
    )

    assert len(matches) == 2


def test_exact_match_is_selected_before_positive_difference():
    matches = match_orders(
        [order("b1", "u1", 150), order("b2", "u2", 100)],
        [order("s1", "u3", 100)],
    )

    assert matches[0].buy_order_id == "b2"


def test_zero_quantity_orders_are_ignored():
    assert (
        match_orders(
            [order("b1", "u1", 100, quantity=0)],
            [order("s1", "u2", 100)],
        )
        == []
    )


def test_empty_book():
    assert match_orders([], []) == []
