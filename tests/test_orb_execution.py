import inspect
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any

import pytest
from pandas import DataFrame, DatetimeIndex

from bot.portfolio import ORB_SIGNAL_CANDLES_MAX, Holding, Strategy
from bot.strategies.shared import TRADING_ZONE, entry_quantity, fractional_allowed


@dataclass
class FakeAsset:
    symbol: str


@dataclass
class FakeOrder:
    asset: FakeAsset
    side: str
    quantity: Decimal | float
    client_order_id: str = ""
    stop_price: float | None = None
    active: bool = True

    def is_active(self) -> bool:
        return self.active


class CancelStrategy(Strategy):
    """Exercises _cancel and _protect without a broker."""

    def __init__(self, resting: list[FakeOrder]) -> None:
        self.parameters = {"fractional_orders": True}
        self._holdings = {}
        self._stops = {}
        self._closing = set()
        self._events = set()
        self.exporter = None
        self.resting = resting
        self.submitted: list[FakeOrder] = []
        self.position = 0.0

    def get_orders(self) -> list[FakeOrder]:
        return [order for order in self.resting if order.active]

    def cancel_open_orders(self, orders: list[FakeOrder]) -> None:
        for order in orders:
            order.active = False

    def sleep(self, seconds: float) -> None:
        return None

    def get_last_price(self, asset: str) -> float:
        return 10.0

    def get_position(self, asset: str) -> Any:
        return None

    def _quantity(self, asset: str) -> float:
        return self.position

    def create_order(self, asset: str, quantity: Any, side: str, **kwargs: Any) -> FakeOrder:
        return FakeOrder(
            FakeAsset(asset),
            side,
            quantity,
            client_order_id=kwargs.get("custom_params", {}).get("client_order_id", ""),
            stop_price=kwargs.get("stop_price"),
        )

    def submit_order(self, order: FakeOrder) -> None:
        self.submitted.append(order)
        self.resting.append(order)


def holding_for(asset: str = "BBD") -> Holding:
    return Holding(
        "orb",
        asset,
        asset,
        10.0,
        9.5,
        0.5,
        10.0,
        datetime(2026, 8, 26, 13, 47, tzinfo=UTC),
        direction=1,
        original_quantity=1000.0,
        lowest=10.0,
    )


# --- shorts settle in whole shares ----------------------------------------


def short_holding(asset: str = "BBD", original: float = 23.0) -> Holding:
    return Holding(
        "orb",
        asset,
        asset,
        10.0,
        10.5,
        0.5,
        10.0,
        datetime(2026, 8, 26, 13, 47, tzinfo=UTC),
        direction=-1,
        original_quantity=original,
        lowest=10.0,
    )


def test_fractional_allowed_only_ever_applies_to_a_long() -> None:
    assert fractional_allowed(1, True) is True
    assert fractional_allowed(1, False) is False
    assert fractional_allowed(-1, True) is False, "a broker lends shares, not fractions"
    assert fractional_allowed(-1, False) is False


def test_a_short_entry_is_sized_in_whole_shares() -> None:
    """Same equity and stop, opposite directions: only the long keeps a fraction."""
    arguments = (100_000.0, 425.80, 5.0, 0.10, 0.01)

    long_size = entry_quantity(*arguments, fractional_allowed(1, True))
    short_size = entry_quantity(*arguments, fractional_allowed(-1, True))

    assert long_size != long_size.to_integral_value(), "the long may hold a fraction"
    assert short_size == short_size.to_integral_value(), "the short may not"
    assert short_size == long_size.to_integral_value(rounding=ROUND_DOWN)


def test_a_short_stop_order_covers_whole_shares() -> None:
    strategy = CancelStrategy([])
    strategy.position = 23.4802
    strategy.parameters = {"fractional_orders": True}

    strategy._protect(short_holding(), 23.4802)

    quantity = Decimal(str(strategy.submitted[-1].quantity))
    assert strategy.submitted[-1].side == "buy", "a short is protected by a buy stop"
    assert quantity == Decimal(23)


def test_a_short_scale_out_rounds_down_and_never_strips_the_stop() -> None:
    """A scale-out worth under a whole share is skipped, stop left in place."""
    stop = FakeOrder(
        FakeAsset("BBD"), "buy", 3.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=10.5
    )
    strategy = CancelStrategy([stop])
    strategy.position = 3.0
    strategy.parameters = {"fractional_orders": True}

    # A quarter of a three-share short is 0.75 — less than one whole share.
    strategy._exit(short_holding(original=3.0), 0.75)

    assert not strategy.submitted, "no zero-quantity order may be sent"
    assert stop.active, "the resting stop must survive a skipped scale-out"


def test_a_long_scale_out_keeps_its_fraction() -> None:
    strategy = CancelStrategy([])
    strategy.position = 1000.0
    strategy.parameters = {"fractional_orders": True}

    strategy._exit(holding_for(), 500.5)

    assert Decimal(str(strategy.submitted[-1].quantity)) == Decimal("500.5")


# --- C4: _protect must not cancel a still-working entry order -------------


def test_protect_leaves_a_working_entry_order_alone() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    strategy = CancelStrategy([entry])
    strategy.position = 1440.0

    strategy._protect(holding_for(), 1440.0)

    assert entry.active, "the unfilled remainder of the entry order was cancelled"


def test_protect_still_replaces_an_existing_stop() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    stop = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    strategy = CancelStrategy([entry, stop])
    strategy.position = 3031.0

    strategy._protect(holding_for(), 3031.0)

    assert not stop.active, "the undersized stop should have been replaced"
    assert entry.active
    assert float(strategy.submitted[-1].quantity) == pytest.approx(3031.0)


def test_cancel_without_a_kind_still_clears_everything() -> None:
    entry = FakeOrder(FakeAsset("BBD"), "buy", 3031.0, client_order_id="mt-o-e-BBD-11672-aaaaaaaa")
    stop = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    strategy = CancelStrategy([entry, stop])

    strategy._cancel("BBD")

    assert not entry.active
    assert not stop.active


def test_cancel_ignores_other_symbols() -> None:
    mine = FakeOrder(
        FakeAsset("BBD"), "sell", 25.0, client_order_id="mt-o-s-BBD-11672-bbbbbbbb", stop_price=9.5
    )
    other = FakeOrder(
        FakeAsset("NKE"), "sell", 10.0, client_order_id="mt-o-s-NKE-11672-cccccccc", stop_price=9.5
    )
    strategy = CancelStrategy([mine, other])

    strategy._cancel("BBD", "s")

    assert not mine.active
    assert other.active


def test_order_kind_reads_the_kind_segment() -> None:
    strategy = CancelStrategy([])

    assert strategy._order_kind("mt-o-s-BBD-11672-bbbbbbbb") == "s"
    assert strategy._order_kind("mt-o-e-BBD-11672-aaaaaaaa") == "e"
    assert strategy._order_kind("mt-o-x-BBD-11672-dddddddd") == "x"
    assert strategy._order_kind("not-a-money-tree-id") is None
    assert strategy._order_kind("") is None


# --- C7: ORB's own risk cap governs its sizing ----------------------------


# A $50 stock with the stop $6 away (12%), so the risk cap binds and the
# notional cap does not:
#   notional cap        100_000 * 0.10 / 50 = 200.00 shares
#   risk cap at 0.005   100_000 * 0.005 / 6 =  83.33 shares  <- the old behaviour
#   risk cap at 0.010   100_000 * 0.010 / 6 = 166.67 shares  <- what the register asks for
WIDE_PRICE = 50.0
WIDE_STOP = 44.0
EQUITY = 100_000.0


class FakeAccount:
    portfolio_value = EQUITY


class FakeApi:
    def get_account(self) -> FakeAccount:
        return FakeAccount()

    def get_all_positions(self) -> list[Any]:
        return []


class FakeBroker:
    api = FakeApi()


class SizingStrategy(Strategy):
    """Drives the real _enter so the risk cap is exercised, not reimplemented."""

    def __init__(self, risk_per_trade_max: float) -> None:
        self.parameters = {
            "fractional_orders": True,
            "position_fraction_max": 0.10,
            "risk_per_trade_max": risk_per_trade_max,
        }
        self._enabled = {"orb", "sma"}
        self._holdings = {}
        self._pending = {}
        self._claims = {}
        self._stops = {}
        self._closing = set()
        self._events = set()
        self._orb_traded = set()
        self._orb_scanned = set()
        self.exporter = None
        self.broker = FakeBroker()
        self.submitted: list[FakeOrder] = []

    def create_order(self, asset: str, quantity: Any, side: str, **kwargs: Any) -> FakeOrder:
        return FakeOrder(
            FakeAsset(asset),
            side,
            quantity,
            client_order_id=kwargs.get("custom_params", {}).get("client_order_id", ""),
        )

    def submit_order(self, order: FakeOrder) -> None:
        self.submitted.append(order)


def enter_wide_stop(strategy: SizingStrategy, engine: str, own_cap: float | None) -> float:
    accepted = strategy._enter(
        engine,
        "WIDE",
        "WIDE",
        WIDE_PRICE,
        WIDE_STOP,
        datetime(2026, 8, 26, 13, 50, tzinfo=UTC),
        risk_fraction_max=own_cap,
    )
    assert accepted
    return float(strategy.submitted[-1].quantity)


def test_orb_uses_its_own_risk_cap_not_the_tighter_global() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    quantity = enter_wide_stop(strategy, "orb", 0.01)

    assert quantity == pytest.approx(EQUITY * 0.01 / (WIDE_PRICE - WIDE_STOP), rel=1e-6)


def test_strategies_without_their_own_cap_keep_the_global() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    quantity = enter_wide_stop(strategy, "sma", None)

    assert quantity == pytest.approx(EQUITY * 0.005 / (WIDE_PRICE - WIDE_STOP), rel=1e-6)


def test_the_notional_cap_still_wins_when_the_stop_is_close() -> None:
    strategy = SizingStrategy(risk_per_trade_max=0.005)

    accepted = strategy._enter(
        "orb",
        "TIGHT",
        "TIGHT",
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 26, 13, 50, tzinfo=UTC),
        risk_fraction_max=0.01,
    )

    assert accepted
    assert float(strategy.submitted[-1].quantity) == pytest.approx(EQUITY * 0.10 / WIDE_PRICE)


# --- C6: one ORB entry per symbol per day, across both breakout engines ---


class TradedStrategy(SizingStrategy):
    """SizingStrategy with both breakout engines enabled."""

    def __init__(self, risk_per_trade_max: float = 0.005) -> None:
        super().__init__(risk_per_trade_max)
        self._enabled = {"orb", "orb_momentum", "sma"}


def enter(strategy: TradedStrategy, engine: str, symbol: str) -> bool:
    return strategy._enter(
        engine,
        symbol,
        symbol,
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 25, 13, 50, tzinfo=UTC),
        risk_fraction_max=0.01 if engine == "orb" else None,
    )


def test_a_filled_entry_is_recorded_against_the_symbol_and_day() -> None:
    strategy = TradedStrategy()

    assert enter(strategy, "orb", "AUR")

    assert (datetime(2026, 8, 25, 13, 50, tzinfo=UTC).date(), "AUR") in strategy._orb_traded


def test_the_scan_skips_a_symbol_already_traded_today() -> None:
    """ORB-10m re-entered AUR 51s after ORB-5m stopped out of it on 2026-08-25.

    The ledger is keyed by (day, symbol) with no engine, so one breakout engine
    entering a name closes it to the other for the rest of the session.
    """
    source = inspect.getsource(Strategy._run_orb_variant)

    assert "(now.date(), symbol) in self._orb_traded" in source
    assert "self._orb_traded: set[tuple[date, str]]" in inspect.getsource(Strategy.initialize)


def test_a_position_restored_mid_session_still_blocks_re_entry() -> None:
    assert "self._orb_traded.add(" in inspect.getsource(Strategy._restore)


def test_the_daily_engines_do_not_write_to_the_traded_ledger() -> None:
    strategy = TradedStrategy()
    strategy._enabled = {"sma"}

    assert strategy._enter(
        "sma",
        "CCK",
        "CCK",
        WIDE_PRICE,
        WIDE_PRICE - 0.10,
        datetime(2026, 8, 25, 13, 50, tzinfo=UTC),
    )

    assert strategy._orb_traded == set()


# --- the breakout is read off the first candle to close outside the range -


def session(closes: list[float], minutes: int = 10) -> DataFrame:
    """A day's completed candles from 09:30, one close each, stamped by start."""
    opens = datetime(2026, 8, 28, 9, 30, tzinfo=TRADING_ZONE)
    index = DatetimeIndex([opens + timedelta(minutes=minutes * i) for i in range(len(closes))])
    return DataFrame({"close": closes}, index=index)


# The opening range of 28 August: 12.85 low, 12.95 high. Price left it on the
# 09:40 candle and kept running, so every later candle also closes above it.
BREAKOUT_HIGH = 12.95
BREAKOUT_LOW = 12.85


def test_the_signal_is_the_first_candle_to_close_outside_the_range() -> None:
    """Not the newest one — reading that entered a candle above the level.

    On 28 August the 09:40 candle closed at 13.05, the first close above the
    range. Its bars had not reached the scan by 09:50, so the newest candle at
    10:00 was read instead and the order went in at 13.42, half a dollar above
    the level it was meant to buy.
    """
    strategy = TradedStrategy()
    candles = session([13.05, 13.42])

    signal = strategy._orb_signal(candles, BREAKOUT_HIGH, BREAKOUT_LOW)

    assert signal == (0, 1, 13.05), "the 09:40 close is the signal, not the 09:50 one"


def test_a_close_back_inside_the_range_is_not_a_signal() -> None:
    strategy = TradedStrategy()

    assert strategy._orb_signal(session([12.90, 12.88]), BREAKOUT_HIGH, BREAKOUT_LOW) is None


def test_a_close_below_the_range_is_a_short_signal() -> None:
    strategy = TradedStrategy()

    signal = strategy._orb_signal(session([12.90, 12.60, 12.40]), BREAKOUT_HIGH, BREAKOUT_LOW)

    assert signal == (1, -1, 12.60)


def test_the_side_is_taken_from_the_signal_candle_not_a_later_reversal() -> None:
    """A breakout that closes below the range first is a short, whatever follows."""
    strategy = TradedStrategy()

    signal = strategy._orb_signal(session([12.60, 13.40]), BREAKOUT_HIGH, BREAKOUT_LOW)

    assert signal is not None and signal[1] == -1


def test_a_breakout_older_than_one_candle_is_passed_over_rather_than_chased() -> None:
    """The rule buys the open after the signal candle; three candles on it is a chase."""
    fresh = session([12.90, 13.05])
    stale = session([13.05, 13.20, 13.35, 13.42])
    strategy = TradedStrategy()

    fresh_signal = strategy._orb_signal(fresh, BREAKOUT_HIGH, BREAKOUT_LOW)
    stale_signal = strategy._orb_signal(stale, BREAKOUT_HIGH, BREAKOUT_LOW)

    assert fresh_signal is not None and len(fresh) - fresh_signal[0] <= ORB_SIGNAL_CANDLES_MAX
    assert stale_signal is not None and len(stale) - stale_signal[0] > ORB_SIGNAL_CANDLES_MAX


def test_one_missed_pass_is_still_recovered() -> None:
    """The scan that follows a late bar may still take it — one candle, no more."""
    strategy = TradedStrategy()
    recovered = session([13.05, 13.42])

    signal = strategy._orb_signal(recovered, BREAKOUT_HIGH, BREAKOUT_LOW)

    assert signal is not None and len(recovered) - signal[0] == ORB_SIGNAL_CANDLES_MAX


# --- targets are cut from the fill, so none of them starts behind it ------


@dataclass
class FilledOrder:
    asset: FakeAsset
    side: str
    avg_fill_price: float


@dataclass
class FilledPosition:
    quantity: float


class FillStrategy(TradedStrategy):
    """Drives the real on_filled_order and _manage_orb without a broker."""

    def __init__(self, price: float) -> None:
        super().__init__()
        self.price = price
        self.exits: list[tuple[str, float | None]] = []

    def get_last_price(self, asset: str) -> float:
        return self.price

    def get_position(self, asset: str) -> Any:
        return FilledPosition(100.0)

    def _protect(self, holding: Holding, quantity: float | None = None) -> None:
        return None

    def _exit(self, holding: Holding, quantity: float | None = None) -> None:
        self.exits.append((holding.asset, quantity))


def filled(engine: str, entry: float, stop: float, price: float) -> FillStrategy:
    """A breakout entry that fills at `entry`, with the market sitting at `price`."""
    strategy = FillStrategy(price)
    now = datetime(2026, 8, 28, 13, 50, tzinfo=UTC)
    assert strategy._enter(engine, "AUR", "AUR", entry, stop, now, direction=1)
    strategy.on_filled_order(
        FilledPosition(100.0), FilledOrder(FakeAsset("AUR"), "buy", entry), entry, 100.0, 1.0
    )
    return strategy


# The 28 August range: 12.85 to 12.95, so the stop sits at 12.925 and the range
# targets sat at 13.00, 13.05 and 13.15 — all three behind a 13.42 fill.
FAR_FILL = 13.42
RANGE_STOP = 12.925


@pytest.mark.parametrize(
    ("engine", "multiples"), [("orb", (1.5, 2.5, 4.0)), ("orb_momentum", (2.0, 4.0, 8.0))]
)
def test_every_target_sits_beyond_a_fill_that_ran_past_the_level(
    engine: str, multiples: tuple[float, ...]
) -> None:
    strategy = filled(engine, FAR_FILL, RANGE_STOP, FAR_FILL)
    holding = strategy._holdings["AUR"]

    assert holding.targets is not None
    assert min(holding.targets) > FAR_FILL
    risk = FAR_FILL - RANGE_STOP
    assert holding.targets == pytest.approx([FAR_FILL + risk * m for m in multiples])


def test_a_fill_past_the_level_does_not_scale_itself_out_on_the_spot() -> None:
    """ORB10 held AUR for one candle on 28 August: entry 13.42, exit 13.21.

    Its targets were cut from the opening range rather than the fill, so all
    three sat below the entry price. The first _manage_orb pass counted the
    first as reached, the next the second, and the trade was flat within three
    minutes without the price going near its 12.925 stop.
    """
    strategy = filled("orb_momentum", FAR_FILL, RANGE_STOP, FAR_FILL)

    strategy._manage_orb(strategy._holdings["AUR"], datetime(2026, 8, 28, 13, 51, tzinfo=UTC))

    assert strategy.exits == [], "no target is reached by the fill that opened the trade"
    assert strategy._holdings["AUR"].stage == 0


def test_the_first_target_still_scales_out_when_the_price_reaches_it() -> None:
    risk = FAR_FILL - RANGE_STOP
    strategy = filled("orb_momentum", FAR_FILL, RANGE_STOP, FAR_FILL + 2.0 * risk)

    strategy._manage_orb(strategy._holdings["AUR"], datetime(2026, 8, 28, 13, 51, tzinfo=UTC))

    assert strategy.exits == [("AUR", 50.0)], "half the position at +2R"
    assert strategy._holdings["AUR"].stage == 1
