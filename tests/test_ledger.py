from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import pytest

from bot.types import STRATEGY_LABELS, RunStatus, RuntimeSnapshot, TradingConfiguration
from ui.dashboard import bot_state
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
    held = still_open["XOM"]
    assert held["strategy"] == "orb"
    assert held["opened"] == "24 Aug"
    # enough to chart the position: where the entry sits, and every fill so far
    assert held["inDate"] == "2026-08-24"
    assert held["inMinute"] == 9 * 60 + 35
    assert [f["s"] for f in held["fills"]] == ["in", "out"]


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


def _snapshot(status: str = "running", strategies: list[str] | None = None) -> RuntimeSnapshot:
    now = datetime.now(UTC)
    return RuntimeSnapshot(
        run_id=UUID("8f558d63-d47d-4a5f-8f77-95b0bf55a591"),
        sequence=1,
        status=cast(RunStatus, status),
        strategies=strategies if strategies is not None else ["orb", "sma"],
        started_at=now - timedelta(minutes=5),
        heartbeat_at=now,
        configuration=TradingConfiguration(
            fractional_orders=True,
            position_fraction_max=0.1,
            risk_per_day_max=0.02,
            risk_per_trade_max=0.005,
        ),
        events=[],
    )


def test_bot_state_marks_the_running_roster_active() -> None:
    state = bot_state(_snapshot(strategies=["orb", "sma"]), stale=False)

    assert state["running"] is True
    assert state["strategies"] == ["orb", "sma"]


def test_bot_state_is_not_running_when_the_heartbeat_went_stale() -> None:
    """A roster from a bot that stopped reporting says what was running, not what is."""
    state = bot_state(_snapshot(), stale=True)

    assert state["running"] is False
    assert state["strategies"] == ["orb", "sma"]


@pytest.mark.parametrize("status", ["starting", "stopped", "failed"])
def test_bot_state_is_not_running_unless_the_status_says_so(status: str) -> None:
    assert bot_state(_snapshot(status=status), stale=False)["running"] is False


def test_bot_state_reports_nothing_running_when_no_snapshot_arrived() -> None:
    state = bot_state(None, stale=True)

    assert state["running"] is False
    assert state["strategies"] == []
    assert state["status"] == "unknown"


def test_bot_state_resolves_the_labels_the_exporter_actually_publishes() -> None:
    """bot/trade.py maps names through STRATEGY_LABELS before publishing them.

    Comparing those labels against engine ids silently matches nothing, which
    reads as every strategy being paused however many are really running.
    """
    published = [STRATEGY_LABELS[name] for name in ("orb", "sma")]
    state = bot_state(_snapshot(strategies=published), stale=False)

    assert state["strategies"] == ["orb", "sma"]


def test_bot_state_still_accepts_a_roster_published_as_ids() -> None:
    state = bot_state(_snapshot(strategies=["orb", "tfb_50"]), stale=False)

    assert state["strategies"] == ["orb", "tfb_50"]


def test_bot_state_keeps_an_unrecognised_roster_entry_visible() -> None:
    assert bot_state(_snapshot(strategies=["mystery"]), stale=False)["strategies"] == ["mystery"]


def test_cycle_records_when_the_trade_opened_as_well_as_when_it_closed() -> None:
    """The log shows both ends, so entry time is carried, not inferred from the hold."""
    cycles, _ = match_cycles(
        [
            fill("NVDA", "buy", "10", "100.00", "2026-08-27T13:33:00Z", "entry"),
            fill("NVDA", "sell", "10", "105.00", "2026-08-27T19:45:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )

    assert cycles[0]["inDate"] == "2026-08-27"
    assert cycles[0]["inMinute"] == 9 * 60 + 33
    assert cycles[0]["date"] == "2026-08-27"
    assert cycles[0]["minute"] == 15 * 60 + 45


def test_an_overnight_hold_reports_the_day_it_opened_not_the_day_it_closed() -> None:
    """A daily engine can hold for days, so the two ends carry their own dates."""
    cycles, _ = match_cycles(
        [
            fill("CAH", "buy", "5", "50.00", "2026-08-24T14:10:00Z", "entry"),
            fill("CAH", "sell", "5", "52.00", "2026-08-27T19:50:00Z", "exit"),
        ],
        [ENTRY, EXIT],
    )

    assert cycles[0]["inDate"] == "2026-08-24"
    assert cycles[0]["inMinute"] == 10 * 60 + 10
    assert cycles[0]["date"] == "2026-08-27"
