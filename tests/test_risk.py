from datetime import date
from decimal import Decimal

import pytest

from money_tree.orb import BreakoutSide
from money_tree.risk import RiskState, size_position


def test_sizes_fractional_long_for_eighty_cent_loss() -> None:
    quantity = size_position(Decimal("100"), Decimal("98"), BreakoutSide.LONG)

    assert quantity == Decimal("0.400000000")


def test_sizes_short_down_to_whole_shares() -> None:
    quantity = size_position(Decimal("100"), Decimal("99.50"), BreakoutSide.SHORT)

    assert quantity == Decimal("1")


def test_returns_zero_when_short_cannot_fit_risk() -> None:
    quantity = size_position(Decimal("100"), Decimal("98"), BreakoutSide.SHORT)

    assert quantity == Decimal("0")


def test_rejects_zero_price_risk() -> None:
    with pytest.raises(ValueError, match="must differ"):
        size_position(Decimal("100"), Decimal("100"), BreakoutSide.LONG)


def test_tracks_realized_and_unrealized_loss() -> None:
    state = RiskState()
    state.record_fill("buy", Decimal("100"), Decimal("0.5"))

    assert state.pnl(Decimal("98")) == Decimal("-1.0")
    assert state.has_daily_loss(Decimal("98"))

    state.record_fill("sell", Decimal("98"), Decimal("0.5"))
    assert state.position_quantity == 0
    assert state.realized_pnl == Decimal("-1.0")


def test_prevents_daily_reset_with_open_position() -> None:
    state = RiskState(position_quantity=Decimal("1"))

    with pytest.raises(RuntimeError, match="position is open"):
        state.reset(date(2026, 8, 13))
