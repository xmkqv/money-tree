"""The rules that decide whether a breakout is worth trading at all.

Every case here is drawn from 2026-08-31, when the five-minute engine took six
breakouts and lost on five of them. The setups are the real opening ranges from
that session, so a threshold moved back to where it was fails these tests.
"""

from datetime import date, datetime

import pytest

from bot.strategies.orb_base import (
    ORB_PRICE_MIN,
    ORB_RISK_CEILING,
    ORB_STOP_FRACTION_MAX,
    ORB_STOP_FRACTION_MIN,
    ORB_TURNOVER_MIN,
    orb_setup,
    range_break,
    relative_volume_ready,
    round_stop,
    session_volume,
)
from bot.strategies.shared import entry_quantity
from tests.world.index import relative_volume_frame


# The six breakouts of 2026-08-31 as the bot saw them: the opening range, the
# close of the candle that broke it, and the price the market order actually
# paid once the scan resolved a couple of minutes later.
@pytest.fixture
def august_31() -> dict[str, tuple[float, float, float, float]]:
    return {
        "ABEV": (2.9000, 2.8950, 2.9050, 2.91),
        "JBLU": (4.7150, 4.6700, 4.6500, 4.64),
        "INFY": (12.0550, 11.8700, 12.0650, 12.02),
        "PBR": (19.3700, 19.1850, 19.3850, 19.44),
        "PCG": (13.5000, 13.0850, 13.5750, 13.5626),
        "PURR": (12.1000, 11.5200, 11.3200, 11.36),
    }


REJECTED = ("ABEV", "JBLU", "INFY", "PBR")
ACCEPTED = ("PCG", "PURR")
EQUITY = 97_842.26


def test_every_breakout_still_reads_as_a_break(
    august_31: dict[str, tuple[float, float, float, float]],
) -> None:
    """The setups were real breaks; they are rejected on their shape, not missed."""
    for symbol, (high, low, close, _) in august_31.items():
        assert range_break(high, low, close) is not None, symbol


@pytest.mark.parametrize("symbol", REJECTED)
def test_the_losing_breakouts_are_now_refused(
    symbol: str, august_31: dict[str, tuple[float, float, float, float]]
) -> None:
    high, low, close, _ = august_31[symbol]

    assert orb_setup(high, low, close) is None


@pytest.mark.parametrize("symbol", ACCEPTED)
def test_the_wide_range_breakouts_are_still_taken(
    symbol: str, august_31: dict[str, tuple[float, float, float, float]]
) -> None:
    high, low, close, price = august_31[symbol]

    setup = orb_setup(high, low, close)

    assert setup is not None
    assert ORB_STOP_FRACTION_MIN <= setup.risk / close <= ORB_STOP_FRACTION_MAX
    assert abs(price - setup.stop) > 0


def test_risk_taken_is_near_uniform_across_the_setups_that_survive(
    august_31: dict[str, tuple[float, float, float, float]],
) -> None:
    """The point of the stop band: the risk budget binds instead of the notional cap.

    On the day, the six trades risked $8 to $258 — a 32x spread — because the
    notional cap always bound and R floated with the opening range.
    """
    risks: list[float] = []
    for symbol in ACCEPTED:
        high, low, close, price = august_31[symbol]
        setup = orb_setup(high, low, close)
        assert setup is not None
        distance = abs(price - setup.stop)
        quantity = entry_quantity(EQUITY, price, distance, 0.10, ORB_RISK_CEILING, True)
        risks.append(float(quantity) * distance)

    assert max(risks) <= EQUITY * ORB_RISK_CEILING
    assert max(risks) / min(risks) < 1.5


@pytest.mark.parametrize(
    ("high", "low", "close", "reason"),
    [
        (10.5, 10.0, 10.2, "no break"),
        (4.20, 4.00, 4.30, "below the price floor"),
        (100.10, 100.00, 100.20, "range too narrow"),
        (100.0, 70.0, 100.10, "stop too wide"),
    ],
)
def test_a_setup_is_refused_for_each_of_its_own_reasons(
    high: float, low: float, close: float, reason: str
) -> None:
    assert orb_setup(high, low, close) is None, reason


def test_a_clean_wide_setup_is_accepted() -> None:
    setup = orb_setup(100.0, 95.0, 100.50)

    assert setup is not None
    assert setup.direction == 1
    assert setup.stop == pytest.approx(98.75)
    assert setup.risk == pytest.approx(1.75)


def test_the_price_floor_is_where_a_penny_stops_dominating_the_stop() -> None:
    assert orb_setup(ORB_PRICE_MIN + 0.10, ORB_PRICE_MIN - 0.10, ORB_PRICE_MIN + 0.20) is not None
    assert orb_setup(ORB_PRICE_MIN - 0.90, ORB_PRICE_MIN - 1.10, ORB_PRICE_MIN - 0.80) is None


# --- stop rounding --------------------------------------------------------


def test_a_stop_rounds_away_from_the_position_never_towards_it() -> None:
    """Rounding to nearest moves a long's stop up half the time, tightening it."""
    assert round_stop(1, 2.8987) == pytest.approx(2.89)
    assert round_stop(-1, 11.6650) == pytest.approx(11.67)
    assert round_stop(1, 12.0087) == pytest.approx(12.00)


def test_a_stop_already_on_the_penny_is_left_where_it_is() -> None:
    assert round_stop(1, 19.32) == pytest.approx(19.32)
    assert round_stop(-1, 4.68) == pytest.approx(4.68)


# --- liquidity ------------------------------------------------------------


def test_relative_volume_needs_turnover_not_just_a_share_count() -> None:
    """A 1M-share session in a $3 stock is $3M of turnover, not a liquid name."""
    day = date(2026, 8, 24)
    clock = datetime(1, 1, 1, 9, 35).time()

    assert relative_volume_ready(relative_volume_frame(day), day, clock, 1.3) is True
    assert relative_volume_ready(relative_volume_frame(day, close=3.0), day, clock, 1.3) is False


def test_session_volume_reports_the_pace_and_the_liquidity_separately() -> None:
    day = date(2026, 8, 24)

    volume = session_volume(relative_volume_frame(day), day, datetime(1, 1, 1, 9, 35).time())

    assert volume is not None
    assert volume.ratio == pytest.approx(1.4)
    assert volume.turnover == pytest.approx(25_000_000.0)
    assert volume.turnover >= ORB_TURNOVER_MIN
