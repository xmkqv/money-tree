from typing import Any

from ui.ledger import match_cycles, order_engine, sessions, summarise


def fill(
    symbol: str,
    side: str,
    qty: str,
    price: str,
    when: str,
    order_id: str = "o1",
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "transaction_time": when,
        "order_id": order_id,
        "id": f"{symbol}{when}",
    }


def order(order_id: str, client_order_id: str) -> dict[str, Any]:
    return {"id": order_id, "client_order_id": client_order_id}


ENTRY = order("entry", "mt-o-e-NVDA-5000-abcd1234")
EXIT = order("exit", "mt-o-x-NVDA-5000-efgh5678")


def test_order_engine_decodes_the_bot_tag() -> None:
    assert order_engine("mt-o-x-BBD-11672-4a24aeef") == "orb"
    assert order_engine("mt-s-e-CLDX-72356-9d980076") == "sma"
    assert order_engine("mt-m-e-AAPL-100-deadbeef") == "orb_momentum"


def test_order_engine_rejects_anything_else() -> None:
    assert order_engine("") is None
    assert order_engine("manual-buy") is None
    assert order_engine("mt-z-e-AAPL-100-deadbeef") is None
    assert order_engine("mt-o-e-AAPL-100") is None


def test_a_long_round_trip_is_one_cycle() -> None:
    cycles, still_open = match_cycles(
        [
            fill("NVDA", "buy", "10", "100.00", "2026-08-24T13:35:00Z", "entry"),
            fill("NVDA", "sell", "10", "103.00", "2026-08-24T18:05:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    assert not still_open
    assert len(cycles) == 1
    assert cycles[0]["side"] == "long"
    assert cycles[0]["strategy"] == "orb"
    assert cycles[0]["pnl"] == 30.0
    assert cycles[0]["entry"] == 100.0
    assert cycles[0]["exit"] == 103.0
    assert cycles[0]["date"] == "2026-08-24"


def test_a_short_round_trip_profits_when_price_falls() -> None:
    cycles, _ = match_cycles(
        [
            fill("META", "sell", "5", "600.00", "2026-08-24T13:40:00Z", "entry"),
            fill("META", "buy", "5", "590.00", "2026-08-24T19:00:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    assert cycles[0]["side"] == "short"
    assert cycles[0]["pnl"] == 50.0


def test_fragmented_fills_collapse_into_a_single_trade() -> None:
    """Fractional sizing splits one position across many fills."""
    cycles, _ = match_cycles(
        [
            fill("AMD", "buy", "4", "100.00", "2026-08-24T13:35:00Z", "entry"),
            fill("AMD", "buy", "6", "105.00", "2026-08-24T13:36:00Z", "entry"),
            fill("AMD", "sell", "3", "110.00", "2026-08-24T17:00:00Z", "exit"),
            fill("AMD", "sell", "7", "112.00", "2026-08-24T17:30:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    assert len(cycles) == 1
    assert cycles[0]["qty"] == 10
    assert cycles[0]["pnl"] == 1114.0 - 1030.0
    assert cycles[0]["entry"] == 103.0
    assert cycles[0]["heldMin"] == 235


def test_untagged_orders_land_in_the_catch_all() -> None:
    cycles, _ = match_cycles(
        [
            fill("AAPL", "buy", "1", "200.00", "2026-08-24T13:35:00Z", "manual"),
            fill("AAPL", "sell", "1", "201.00", "2026-08-24T17:35:00Z", "manual"),
        ],
        [order("manual", "some-ui-order")],
    )
    assert cycles[0]["strategy"] == "unattributed"


def test_a_position_still_held_is_not_a_closed_trade() -> None:
    cycles, still_open = match_cycles(
        [
            fill("XOM", "buy", "12", "112.65", "2026-08-24T13:35:00Z", "entry"),
            fill("XOM", "sell", "5", "114.00", "2026-08-25T17:00:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    assert cycles == []
    assert still_open == {"XOM": {"strategy": "orb", "opened": "24 Aug"}}


def test_reopening_after_flat_starts_a_new_cycle() -> None:
    cycles, _ = match_cycles(
        [
            fill("CCK", "buy", "2", "100.00", "2026-08-24T13:35:00Z", "entry"),
            fill("CCK", "sell", "2", "102.00", "2026-08-24T17:00:00Z", "exit"),
            fill("CCK", "buy", "2", "101.00", "2026-08-25T13:35:00Z", "entry"),
            fill("CCK", "sell", "2", "99.00", "2026-08-25T17:00:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    assert [c["pnl"] for c in cycles] == [4.0, -4.0]
    assert [c["date"] for c in cycles] == ["2026-08-24", "2026-08-25"]


def test_summarise_counts_break_even_as_a_loss() -> None:
    cycles, _ = match_cycles(
        [
            fill("A", "buy", "1", "10.00", "2026-08-24T13:35:00Z", "entry"),
            fill("A", "sell", "1", "10.00", "2026-08-24T17:00:00Z", "exit"),
            fill("B", "buy", "1", "10.00", "2026-08-24T13:35:00Z", "entry"),
            fill("B", "sell", "1", "12.00", "2026-08-24T17:00:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    stats = summarise(cycles)
    assert stats == {"n": 2, "wins": 1, "losses": 1, "net": 2.0, "gross": 2.0, "bleed": 0.0}


def test_sessions_key_each_day_to_the_prior_close() -> None:
    cycles, _ = match_cycles(
        [
            fill("A", "buy", "1", "10.00", "2026-08-24T13:35:00Z", "entry"),
            fill("A", "sell", "1", "15.00", "2026-08-24T17:00:00Z", "exit"),
            fill("B", "buy", "1", "10.00", "2026-08-25T13:35:00Z", "entry"),
            fill("B", "sell", "1", "8.00", "2026-08-25T17:00:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )
    rows = sessions(cycles, {"2026-08-24": 1005.0}, opening=1000.0)
    assert [(r["date"], r["pnl"], r["before"], r["wins"]) for r in rows] == [
        ("2026-08-24", 5.0, 1000.0, 1),
        ("2026-08-25", -2.0, 1005.0, 0),
    ]
