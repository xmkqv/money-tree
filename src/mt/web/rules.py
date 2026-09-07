from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypedDict

from mt.config.settings import settings
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.daily import Daily
from mt.strategies.keys import StrategyKey


class Row(TypedDict):
    field: str
    value: str
    source: str


RULE_FIELDS = (
    "Market",
    "Sentiment",
    "Direction",
    "Range",
    "Setup",
    "Confirmation",
    "Sorting",
    "Entry",
    "Stop Loss",
    "Max Risk",
    "Min. R:R",
    "Exit Rule",
    "Emergency Exit",
)
KINDS = {"breakout": "Intraday breakout", "daily": "Daily trend"}


def millions(value: float) -> str:
    return f"${value / 1_000_000:g}M"


def percent(fraction: float) -> str:
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


MARKET = (
    f"US common stocks screened daily: share price ${settings.screen.price_usd_min:.0f} or "
    f"more, turnover {millions(settings.screen.turnover_usd_min)} or more averaged across the "
    f"last {settings.screen.turnover_sessions} completed sessions, and tradable and "
    "fractionable at Alpaca."
)


@dataclass(frozen=True, slots=True)
class DailyProse:
    setup: str
    setup_source: str
    confirmation: str
    entry: str
    entry_source: str
    market: str = MARKET
    market_source: str = "portfolio.py · _screen"
    risk_source: str = "portfolio.py · enter"


DAILY_PROSE: dict[StrategyKey, DailyProse] = {
    "daily_sma": DailyProse(
        setup=(
            f"The closing price crosses back above its {settings.daily.average_sessions}-day "
            f"average while the trend is already stacked underneath it: price above the "
            f"{settings.daily_sma.trend_sessions}-day average, and that average above the "
            f"{settings.daily_sma.trend_sessions_long}-day. Needs "
            f"{settings.daily_sma.trend_sessions_long} sessions of past bars."
        ),
        setup_source="strategies/daily_sma.py · does_enter",
        confirmation=(
            f"RSI ({settings.indicators.period}) at {settings.daily_sma.rsi_min:g} or above, and "
            f"ADX ({settings.indicators.period}) at {settings.daily_sma.adx_min:g} or above."
        ),
        entry=(
            f"A three-day structure: one session closes below the "
            f"{settings.daily.average_sessions}-day average, the next closes back above it and "
            "higher than that first close, and the buy "
            "goes in at the open of the third. Market buy, retried every iteration until the "
            f"close. Skipped if the company reports earnings within "
            f"{settings.earnings.block_days} days. A "
            "company with no earnings date on file can still be bought. A company whose calendar "
            "cannot be read at all is left for that session."
        ),
        entry_source="strategies/daily_sma.py · does_enter, strategies/daily.py · run",
    ),
    "daily_tfb": DailyProse(
        market=(
            f"{MARKET} This strategy screens that list again on its own floors: share price "
            f"${settings.screen.price_usd_min:.0f} or more, and turnover of "
            f"{millions(settings.screen.turnover_usd_min)} or more averaged across the last "
            f"{settings.daily_tfb.turnover_sessions} completed sessions. Turnover here is "
            "the value traded in each session, which is that session's close times its share "
            "volume. A symbol whose sessions cannot be read does not pass."
        ),
        market_source="portfolio.py · _screen, strategies/daily_tfb.py · does_clear",
        setup=(
            f"The closing price is above its {settings.daily_tfb.trend_sessions}-day average, "
            f"that average is higher than it was {settings.daily_tfb.average_lag_sessions} "
            "sessions ago, and the close beats the previous session's high."
        ),
        setup_source="strategies/daily_tfb.py · does_enter",
        confirmation=(
            f"ADX ({settings.indicators.period}) at {settings.daily_tfb.adx_min:g} or above."
        ),
        entry=(
            "Market buy at the open, then retried every iteration until the close. The "
            "setup is cut from completed sessions, so the day's list is scanned once and "
            "re-offered. A symbol that could not be funded at the open is taken later in the "
            "day if room frees up. It may have missed out because no slot was left, because "
            "no affordable size was available, or because another strategy held it. Upcoming "
            "earnings do not block an entry for this strategy."
        ),
        entry_source="strategies/daily.py · run",
        risk_source="strategies/daily.py · run, portfolio.py · enter",
    ),
}


def strategy_rows(
    cls: type[Strategy], per_trade: float, opens: datetime, closes: datetime
) -> list[Row]:
    if issubclass(cls, Breakout):
        return _breakout_rows(cls, per_trade, opens, closes)
    if issubclass(cls, Daily):
        return _daily_rows(cls, per_trade, closes)
    raise ValueError(f"{cls.__name__} has no rules")


def max_risk_row(cls: type[Strategy], per_trade: float, source: str) -> Row:
    own = cls.risk_fraction_max
    limit = per_trade if own is None else own
    return Row(
        field="Max Risk",
        value=f"{percent(limit)} of account equity per trade"
        + (
            ", which is the configured per-trade limit. This strategy states none of its own."
            if own is None
            else f". This strategy states its own {percent(own)}, so that governs instead of the "
            f"configured {percent(per_trade)}."
        )
        + f" A single position is never worth more than "
        f"{percent(settings.risk.position_fraction_max)} of equity, and this strategy holds at "
        f"most {cls.positions_max} positions at once.",
        source=source,
    )


def _breakout_rows(
    cls: type[Breakout], per_trade: float, opens: datetime, closes: datetime
) -> list[Row]:
    breakout = settings.breakout
    period = settings.indicators.period
    minutes = cls.opening_minutes
    opening_end = f"{opens + timedelta(minutes=minutes):%H:%M}"
    first_entry = f"{opens + timedelta(minutes=2 * minutes):%H:%M}"
    scan_end = f"{opens + timedelta(minutes=breakout.scan_minutes):%H:%M}"
    exit_at = f"{closes - timedelta(minutes=breakout.close_lead_minutes):%H:%M}"
    exit_before = f"{closes - timedelta(minutes=breakout.close_lead_minutes - 1):%H:%M}"

    confirmation = (
        f"Volume traded up to the signal candle's close is at least "
        f"{cls.volume_multiple:g}x the "
        f"{breakout.past_sessions}-session average at the same time of day, and that "
        f"average session turns over at least {millions(settings.screen.turnover_usd_min)}. "
        f"All {breakout.past_sessions} earlier sessions must be available to compare "
        "against. "
        "If fewer are available there is no confirmation, and the breakout is passed over. "
        "The reading is taken at the signal candle's close rather than at the moment the "
        "scan runs, so a breakout found on a late pass is still confirmed on the volume that "
        "made it. Each session is measured between its own opening and closing bell, so a "
        "half day is compared as a half day."
    )

    first, second, third = cls.target_multiples
    multiples = f"{first:g}x, {second:g}x and {third:g}x"
    reward = f"{first:g}:1 at the first target, then {second:g}:1 and {third:g}:1."
    targets = (
        f"Targets are re-cut from the filled price: {multiples} the risk actually taken. A "
        "fill away from the signal price moves the targets with it."
    )

    extension = (
        ""
        if cls.entry_extension_max is None
        else f" It is also passed over if that live quote sits more than "
        f"{percent(cls.entry_extension_max)} of the opening range beyond the breakout "
        "level. The stop "
        "is a fixed distance inside the range, so a price further past the level risks more "
        "and leaves less of the move to collect."
    )

    return [
        Row(field="Market", value=MARKET, source="portfolio.py · _screen"),
        Row(
            field="Sentiment",
            value="None. This strategy takes signals whatever the wider market is doing.",
            source="strategies/breakout.py · run",
        ),
        Row(
            field="Direction",
            value="Long and short. A short is skipped when the broker will not lend the "
            "stock. A short is sized in whole shares, because a broker lends whole shares "
            "only, so every order on a short leg is rounded down to a whole number. Longs "
            "use fractional quantities when the account allows them.",
            source="portfolio.py · enter, protect, exit",
        ),
        Row(
            field="Range",
            value=f"The opening range is the first {minutes}-minute candle, from the "
            f"opening bell to {opening_end}. The last trade before {opening_end} closes "
            "it. Its high "
            "and low set the levels for the day. The bell is read from the exchange "
            "calendar, so a late open moves the range with it.",
            source="strategies/breakout.py · run, exchange.py · session_bounds",
        ),
        Row(
            field="Setup",
            value=f"The first completed {minutes}-minute candle since the range that closes "
            "above the range high (long) or below the range low (short). A candle still "
            f"forming never signals. Checked every {minutes} minutes from {opening_end}, "
            f"when the opening candle closes, to {scan_end}, at most once per stock per "
            "day. Every "
            "pass re-reads the whole session since the range rather than only its newest "
            "candle, so a breakout whose bars reached the scan late still supplies the "
            "signal "
            f"candle. It must be one of the last {breakout.signal_candles_max} completed "
            f"candles, which is {breakout.signal_candles_max * minutes} minutes of the move. "
            "An older close "
            "has already run, and is passed over. Once either breakout strategy has traded "
            "a stock, both leave it alone for the rest of the session. The range itself "
            f"must be at least {percent(breakout.range_fraction_min)} of the price, and the "
            f"stop cut from it must fall between {percent(breakout.stop_fraction_min)} and "
            f"{percent(breakout.stop_fraction_max)} of the price. A narrower range puts the "
            "stop "
            "inside the spread.",
            source="strategies/breakout.py · run, is_setup_ready",
        ),
        Row(
            field="Confirmation",
            value=confirmation,
            source="strategies/breakout.py · is_confirmed",
        ),
        Row(
            field="Sorting",
            value="Ranked by the value traded in the last completed daily session, which is "
            "its close times its share volume, highest first. When more breakouts fire than "
            "there is room to hold, the busiest take the slots. This is a different question "
            "from the confirmation above, which measures each stock against its own past "
            "rather than against other stocks.",
            source="strategies/base.py · ranked",
        ),
        Row(
            field="Entry",
            value="A market order goes in the moment the scan reads the breakout, and fills "
            f"at the next executable price. That is the open of the next {minutes}-minute "
            f"candle when the signal is read on its own boundary, and {first_entry} at the "
            "earliest, because the opening candle cannot break its own range. Good for the "
            "day only. The size is worked out from the live quote, and falls back to the "
            "breakout candle's close. The fill then sets the entry, the risk and the "
            "targets. "
            "The entry is passed over if another strategy already holds the stock, if the "
            "account is at its position cap or fully invested, if the size that fits the "
            "risk "
            f"limits comes to less than ${settings.risk.notional_usd_min:.0f}, or if that "
            "live quote has "
            f"already run back through the stop the breakout would have been given."
            f"{extension}",
            source="portfolio.py · on_trading_iteration, enter",
        ),
        Row(
            field="Stop Loss",
            value=f"{percent(breakout.long_stop_fraction)} of the way back into "
            f"the opening range for a long, {percent(breakout.short_stop_fraction)} "
            "for a short. Once the first target is hit, the stop trails "
            f"{breakout.trail_atr_multiple:g}x the {period}-period ATR behind the best price "
            f"the trade has seen, and never moves back past the entry price. That "
            f"ATR({period}) "
            f"is calculated from {minutes}-minute candles across trading sessions, using "
            "prior-session bars where they are available, so overnight gaps contribute to "
            f"true range. At least {breakout.trail_bars_min} completed {minutes}-minute "
            "candles "
            "must be available. Prior sessions count towards that total, so the trade "
            "normally starts with enough. The level rests as an order at the broker. It "
            "is replaced whenever it moves, and re-sent if it stops covering the whole "
            "position. A level the market has already reached cannot rest as an order. When "
            "the stop lands at or beyond the last price, the whole position is closed at "
            "market instead. The move to breakeven after the first target is the usual way "
            "this happens. Price back at the entry means the stop is hit, so the position "
            "leaves at market.",
            source="strategies/breakout.py · run, manage, portfolio.py · protect",
        ),
        max_risk_row(cls, per_trade, "portfolio.py · enter"),
        Row(
            field="Min. R:R",
            value=f"{reward} {targets}",
            source="portfolio.py · on_filled_order",
        ),
        Row(
            field="Exit Rule",
            value="Scaled out in three: half the position as first filled at the first "
            "target, a quarter of it at the second, the remainder at the third. On a short "
            "each slice is rounded down to whole shares, and a slice worth less than a "
            "single "
            "share is skipped. The resting stop still covers the position, and the next "
            "target or the closing deadline takes it. The trailing stop takes whatever is "
            "left if price turns first.",
            source="strategies/breakout.py · manage",
        ),
        Row(
            field="Emergency Exit",
            value=f"Everything is closed before {exit_before}. The exit is sent at "
            f"{exit_at}, "
            f"which is {breakout.close_lead_minutes} minutes before the closing bell the "
            "exchange "
            "calendar gives for the session, so the market order fills in time and a half "
            "day "
            "closes on its own clock. This strategy never holds overnight. The daily loss "
            "limit closes all positions and stops new entries for the rest of the day.",
            source="strategies/breakout.py · manage, portfolio.py · _is_daily_loss_reached",
        ),
    ]


def _daily_rows(cls: type[Daily], per_trade: float, closes: datetime) -> list[Row]:
    prose = DAILY_PROSE[cls.key]
    lead_minutes = settings.earnings.exit_lead_minutes
    period = settings.indicators.period
    average_sessions = settings.daily.average_sessions
    earnings_exit = f"{closes - timedelta(minutes=lead_minutes):%H:%M}"
    return [
        Row(field="Market", value=prose.market, source=prose.market_source),
        Row(
            field="Sentiment",
            value=f"{settings.benchmark_symbol} must be trading above its own "
            f"{average_sessions}-day average. If it is not, no daily strategy takes a "
            "position that day.",
            source="strategies/daily.py · run",
        ),
        Row(field="Direction", value="Long only.", source="portfolio.py · enter"),
        Row(
            field="Range",
            value="Not used. This strategy reads daily candles and has no opening range.",
            source="strategies/daily.py · run",
        ),
        Row(field="Setup", value=prose.setup, source=prose.setup_source),
        Row(field="Confirmation", value=prose.confirmation, source=prose.setup_source),
        Row(
            field="Sorting",
            value="Ranked by the value traded in the last completed session, which is its "
            "close times its share volume, highest first. When more symbols qualify on the "
            "same morning than there is room to hold, the busiest take the slots. A symbol "
            "whose session cannot be read ranks last but still trades.",
            source="strategies/daily.py · _ranked",
        ),
        Row(field="Entry", value=prose.entry, source=prose.entry_source),
        Row(
            field="Stop Loss",
            value=f"{cls.stop_atr_multiple:g}x the {period}-period ATR below the entry "
            f"price, then trailing {cls.stop_atr_multiple:g}x ATR below the highest close "
            "reached since entry. The stop only ever moves up.",
            source="strategies/daily.py · manage",
        ),
        max_risk_row(cls, per_trade, prose.risk_source),
        Row(
            field="Min. R:R",
            value="No fixed target. The trade is held while the trend holds and closed on "
            "the exit rule below, so no reward-to-risk ratio is set in advance.",
            source="strategies/daily.py · manage",
        ),
        Row(
            field="Exit Rule",
            value="Closed when the price falls through the trailing stop, or when the close "
            f"drops below its {average_sessions}-day average, or RSI ({period}) falls under "
            f"{settings.daily.exit_rsi_max:g}. Either one is enough on its own.",
            source="strategies/daily.py · does_signal_exit",
        ),
        Row(
            field="Emergency Exit",
            value=(
                f"Closed {lead_minutes} minutes before the closing bell "
                f"({earnings_exit} on a full session) on the session before the company "
                "reports earnings, unless that calendar cannot be read, in which case the "
                "position is left alone. The daily loss limit closes all positions and "
                "stops new entries for the rest of the day."
                if cls.does_heed_earnings
                else "The daily loss limit closes all positions and stops new entries for "
                "the rest of the day. Earnings do not close a position for this strategy. "
                "It holds through the report and leaves on its stop or its exit rule."
            ),
            source="strategies/daily.py · manage, portfolio.py · _is_daily_loss_reached",
        ),
    ]
