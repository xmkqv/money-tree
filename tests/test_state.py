from datetime import date
from decimal import Decimal

import pytest

from money_tree.broker import AccountSnapshot, verify_account_snapshot
from money_tree.risk import RiskState
from money_tree.state import StateStore


def test_round_trips_live_state(tmp_path) -> None:
    path = tmp_path / "state.json"
    expected = RiskState(
        trading_date=date(2026, 8, 13),
        traded=True,
        realized_pnl=Decimal("-0.25"),
        position_quantity=Decimal("0.5"),
        average_entry_price=Decimal("100"),
        stop_price=Decimal("98.40"),
        stop_order_id="stop-id",
    )

    StateStore(path).save(expected)

    assert StateStore(path).load() == expected


def test_rejects_unknown_spy_order() -> None:
    snapshot = AccountSnapshot(None, frozenset({"foreign-order"}))

    with pytest.raises(RuntimeError, match="does not own"):
        verify_account_snapshot(snapshot, RiskState())


def test_rejects_unowned_spy_position() -> None:
    snapshot = AccountSnapshot(Decimal("1"), frozenset())

    with pytest.raises(RuntimeError, match="does not own"):
        verify_account_snapshot(snapshot, RiskState())


def test_clears_stale_position_when_broker_is_flat() -> None:
    state = RiskState(
        position_quantity=Decimal("0.5"),
        average_entry_price=Decimal("100"),
        stop_price=Decimal("98"),
        stop_order_id="missing-stop",
    )

    verify_account_snapshot(AccountSnapshot(None, frozenset()), state)

    assert state.position_quantity == 0
    assert state.stop_order_id is None
