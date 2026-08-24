from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pandas import DataFrame, DatetimeIndex, Series

from bot.strategies import shared
from bot.strategies.orb_base import relative_volume_ready
from bot.strategies.shared import (
    TRADING_ZONE,
    earnings_blocked,
    earnings_exit_due,
    entry_quantity,
    latest_atr,
    market_is_rising,
    momentum_entry,
    next_stop,
    normalize_ohlcv,
)
from tests.world.index import market_frame, relative_volume_frame


def test_market_data_is_normalized_when_frame_is_valid() -> None:
    frame = market_frame(3).sort_index(ascending=False)
    original = frame.copy(deep=True)

    normalized = normalize_ohlcv(frame, {"high", "low", "close", "volume"})

    assert normalized.index.is_monotonic_increasing
    assert normalized.index.tz == TRADING_ZONE
    assert frame.equals(original)


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (DataFrame({"close": [1.0]}), "DatetimeIndex"),
        (
            DataFrame(
                {"close": [1.0, 2.0]},
                index=DatetimeIndex([datetime(2026, 1, 1, tzinfo=UTC)] * 2),
            ),
            "timestamps must be unique",
        ),
        (
            DataFrame(
                {"close": ["bad"]},
                index=DatetimeIndex([datetime(2026, 1, 1, tzinfo=UTC)]),
            ),
            "must be numeric",
        ),
    ],
)
def test_market_data_is_rejected_when_frame_breaks_contract(frame: DataFrame, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        normalize_ohlcv(frame, {"close"})


def test_market_data_is_rejected_when_required_column_is_missing() -> None:
    with pytest.raises(ValueError, match="missing required columns: adjusted"):
        normalize_ohlcv(market_frame(3), {"close", "volume", "adjusted"})


def test_position_size_respects_tighter_risk_limit_when_inputs_are_valid() -> None:
    quantity = entry_quantity(10_000, 100, 5, 0.1, 0.005, True)

    assert quantity == Decimal("10.000000000")


def test_position_size_rounds_down_when_fractional_orders_are_disabled() -> None:
    quantity = entry_quantity(10_000, 333, 10, 0.2, 0.02, False)

    assert quantity == Decimal("6")


@pytest.mark.parametrize(
    ("equity", "price", "stop_distance"),
    [(0.0, 100.0, 5.0), (10_000.0, -1.0, 5.0), (10_000.0, 100.0, float("inf"))],
)
def test_position_size_is_zero_when_inputs_are_not_tradable(
    equity: float, price: float, stop_distance: float
) -> None:
    assert entry_quantity(equity, price, stop_distance, 0.1, 0.005, True) == Decimal(0)


def test_position_size_is_zero_when_notional_is_below_broker_minimum() -> None:
    assert entry_quantity(0.5, 100, 1, 1.0, 1.0, True) == Decimal(0)


def test_stop_only_tightens_when_candidate_moves_with_position() -> None:
    assert next_stop(1, 95.0, 97.0) == 97.0
    assert next_stop(1, 95.0, 93.0) == 95.0
    assert next_stop(-1, 105.0, 103.0) == 103.0
    assert next_stop(-1, 105.0, 107.0) == 105.0


def test_atr_is_positive_when_price_history_is_sufficient() -> None:
    assert latest_atr(market_frame(20)) > 0


def test_atr_is_rejected_when_price_history_is_insufficient() -> None:
    with pytest.raises(ValueError, match="ATR requires at least 14 price bars"):
        latest_atr(market_frame(5))


def test_market_rises_when_latest_close_exceeds_twenty_day_average() -> None:
    assert market_is_rising(market_frame(30)) is True


def test_market_does_not_rise_when_history_is_insufficient() -> None:
    assert market_is_rising(market_frame(10)) is False


def test_momentum_entry_passes_when_every_threshold_is_met() -> None:
    frame = market_frame(200)

    def average(close: Series, length: int, talib: bool) -> Series:
        values = {20: 250.0, 50: 200.0, 200: 100.0}
        return Series(values[length], index=close.index)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(shared, "ta_sma", average)
        monkeypatch.setattr(
            shared,
            "ta_rsi",
            lambda close, length, talib: Series(60.0, index=close.index, name="RSI_14"),
        )
        monkeypatch.setattr(
            shared,
            "ta_adx",
            lambda high, low, close, length, talib: DataFrame(
                {"ADX_14": Series(30.0, index=close.index)}
            ),
        )
        monkeypatch.setattr(
            shared,
            "ta_cross",
            lambda close, threshold, above, asint: Series(1.0, index=close.index),
        )

        assert momentum_entry(frame) is True


def test_momentum_entry_fails_when_history_is_insufficient() -> None:
    assert momentum_entry(market_frame(199)) is False


def test_relative_volume_passes_when_current_session_exceeds_threshold() -> None:
    day = date(2026, 8, 24)

    assert relative_volume_ready(
        relative_volume_frame(day), day, datetime(1, 1, 1, 9, 35).time(), 1.3
    )


def test_relative_volume_fails_when_twenty_session_history_is_unavailable() -> None:
    day = date(2026, 8, 24)

    assert (
        relative_volume_ready(
            relative_volume_frame(day, history_sessions=19),
            day,
            datetime(1, 1, 1, 9, 35).time(),
            1.3,
        )
        is False
    )


def test_earnings_rules_block_entry_and_schedule_prior_session_exit() -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(shared, "earnings_dates", lambda symbol: (date(2026, 8, 31),))

        assert earnings_blocked("AAPL", date(2026, 8, 27)) is True
        assert earnings_exit_due("AAPL", date(2026, 8, 28)) is True


def test_earnings_rules_do_not_exit_when_no_earnings_are_known() -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(shared, "earnings_dates", lambda symbol: ())

        assert earnings_exit_due("AAPL", date(2026, 8, 28)) is False
