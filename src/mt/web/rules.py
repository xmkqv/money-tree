from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypedDict

from mt.config.settings import RuleSettings
from mt.config.values import StrategyKey
from mt.strategies.base import Strategy
from mt.strategies.breakout import Breakout
from mt.strategies.daily import Daily


class Row(TypedDict):
    field: str
    value: str
    source: str


RULE_FIELDS = (
    "Symbols",
    "Market condition",
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


def symbols(settings: RuleSettings) -> str:
    return (
        f"US common stocks screened daily: share price ${settings.screen.price_usd_min:.0f} or "
        f"more, turnover {millions(settings.screen.turnover_usd_min)} or more averaged across the "
        f"last {settings.screen.turnover_sessions} completed sessions, and tradable and "
        "fractionable at the broker."
    )


@dataclass(frozen=True, slots=True)
class DailyProse:
    setup: str
    setup_source: str
    confirmation: str
    entry: str
    entry_source: str
    symbols: str = ""
    symbols_source: str = "portfolio.py · _screen"
    risk_source: str = "portfolio.py · enter"


def daily_prose(settings: RuleSettings) -> dict[StrategyKey, DailyProse]:
    return {
        "daily_sma": DailyProse(
            setup=(
                f"The closing price crosses above its {settings.daily.average_sessions}-day "
                f"average. The price is above the "
                f"{settings.daily_sma.trend_sessions}-day average, and that average above the "
                f"{settings.daily_sma.trend_sessions_long}-day average. Requires "
                f"{settings.daily_sma.trend_sessions_long} sessions of historical bars."
            ),
            setup_source="strategies/daily_sma.py · does_enter",
            confirmation=(
                f"RSI ({settings.indicators.period}) at {settings.daily_sma.rsi_min:g} "
                "or above, and "
                f"ADX ({settings.indicators.period}) at {settings.daily_sma.adx_min:g} or above."
            ),
            entry=(
                f"A three-day structure: one session closes below the "
                f"{settings.daily.average_sessions}-day average, the next closes back above it and "
                "higher than that first close, and the buy "
                "goes in at the open of the third. Market buy, retried every iteration until the "
                "close."
            ),
            entry_source="strategies/daily_sma.py · does_enter, strategies/daily.py · run",
        ),
        "daily_tfb": DailyProse(
            symbols=(
                f"{symbols(settings)} This strategy screens that list again on turnover: "
                f"{millions(settings.screen.turnover_usd_min)} or more averaged across the last "
                f"{settings.daily_tfb.turnover_sessions} completed sessions. Turnover here is "
                "the value traded in each session, which is that session's close times its share "
                "volume. A symbol whose sessions cannot be read does not pass."
            ),
            symbols_source="portfolio.py · _screen, strategies/daily_tfb.py · does_clear",
            setup=(
                f"The closing price is above its {settings.daily_tfb.trend_sessions}-day average, "
                f"that average is higher than it was {settings.daily_tfb.trend_lag_sessions} "
                "sessions ago, and the close beats the previous session's high."
            ),
            setup_source="strategies/daily_tfb.py · does_enter",
            confirmation=(
                f"ADX ({settings.indicators.period}) at {settings.daily_tfb.adx_min:g} or above."
            ),
            entry=(
                "Submit a market buy at the open. Retry each iteration until the close if "
                "entry limits prevent the order. Scan completed sessions once per day."
            ),
            entry_source="strategies/daily.py · run",
            risk_source="strategies/daily.py · run, portfolio.py · enter",
        ),
    }


def strategy_rows(
    cls: type[Strategy], settings: RuleSettings, opens: datetime, closes: datetime
) -> list[Row]:
    if issubclass(cls, Breakout):
        return _breakout_rows(cls, settings, opens, closes)
    if issubclass(cls, Daily):
        return _daily_rows(cls, settings, closes)
    raise ValueError(f"{cls.__name__} has no rules")


def max_risk_row(cls: type[Strategy], settings: RuleSettings, source: str) -> Row:
    per_trade = settings.risk.per_trade_max
    own = cls.equity_risk_fraction_max
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
    cls: type[Breakout], settings: RuleSettings, opens: datetime, closes: datetime
) -> list[Row]:
    breakout = settings.breakout
    period = settings.indicators.period
    minutes = cls.opening_minutes
    opening_at, scan_at = cls.entry_window(opens, closes)
    opening_end = f"{opening_at:%H:%M}"
    first_entry = f"{min(closes, opens + timedelta(minutes=2 * minutes)):%H:%M}"
    scan_end = f"{scan_at:%H:%M}"
    exit_at = f"{closes - timedelta(minutes=breakout.close_lead_minutes):%H:%M}"

    confirmation = (
        f"Volume traded up to the signal bar's close is at least "
        f"{cls.volume_multiple:g}x the "
        f"{breakout.lookback_sessions}-session average at the same time of day. "
        f"Requires {breakout.lookback_sessions} earlier sessions. "
        "Use volume at the signal close, including when bars arrive late. "
        "Include only regular trading hours for each session."
    )

    first, second, third = cls.target_multiples
    multiples = f"{first:g}x, {second:g}x and {third:g}x"
    reward = f"{first:g}:1 at the first target, then {second:g}:1 and {third:g}:1."
    targets = f"Targets use the average fill price and {multiples} the distance from entry to stop."

    extension = (
        ""
        if cls.entry_extension_max is None
        else f" Skip the entry if the realtime quote is more than "
        f"{percent(cls.entry_extension_max)} of the opening range beyond the breakout "
        "level."
    )

    return [
        Row(field="Symbols", value=symbols(settings), source="portfolio.py · _screen"),
        Row(
            field="Market condition",
            value="None. This strategy takes signals whatever the wider market is doing.",
            source="strategies/breakout.py · run",
        ),
        Row(
            field="Direction",
            value="Long and short. A short is skipped when the broker will not lend the "
            "stock. Every order is sized in whole shares and rounded down, so a leg worth "
            "less than one share is skipped.",
            source="portfolio.py · enter, protect, exit",
        ),
        Row(
            field="Range",
            value=f"The opening range is the first {minutes}-minute bar, from the "
            f"opening bell to {opening_end}. The last trade before {opening_end} closes "
            "it. Its high "
            "and low set the levels for the day. The bell is read from the exchange "
            "calendar, so a late open moves the range with it.",
            source="strategies/breakout.py · run, exchange.py · session_bounds",
        ),
        Row(
            field="Setup",
            value=f"The first completed {minutes}-minute bar since the range that closes "
            "above the range high (long) or below the range low (short). A bar still "
            f"forming never signals. Checked every {minutes} minutes from {opening_end}, "
            f"when the opening bar closes, to {scan_end}, at most once per stock per "
            "day. Every "
            "pass re-reads the whole session since the range rather than only its newest "
            "bar, so a breakout whose bars reached the scan late still supplies the "
            "signal "
            f"bar. It must be one of the last {breakout.signal_bars_max} completed "
            f"bars, which is {breakout.signal_bars_max * minutes} minutes of the move. "
            "An older close "
            "has already run, and is passed over. Once this strategy has traded a stock, it "
            "leaves it alone for the rest of the session. The range itself "
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
            "its close times its share volume, highest first.",
            source="strategies/base.py · ranked",
        ),
        Row(
            field="Entry",
            value="A market order goes in the moment the scan reads the breakout, and fills "
            f"at the next executable price. That is the open of the next {minutes}-minute "
            f"bar when the signal is read on its own boundary, and {first_entry} at the "
            "earliest, because the opening bar cannot break its own range. Good for the "
            "day only. The size is worked out from the realtime quote, and falls back to the "
            "breakout bar's close. The fill then sets the entry, the stop distance and the "
            "targets. "
            "The entry is passed over if another strategy already holds the stock, if the "
            "account is at its position cap or fully invested, if the size that fits the "
            "risk "
            f"limits comes to less than ${settings.risk.notional_usd_min:.0f}, or if that "
            "realtime quote has "
            f"already run back through the stop the breakout would have been given."
            f"{extension}",
            source="portfolio.py · on_trading_iteration, enter",
        ),
        Row(
            field="Stop Loss",
            value=f"Measured from the opening range low to its high: "
            f"{percent(breakout.long_stop_fraction)} for a long, "
            f"{percent(breakout.short_stop_fraction)} for a short. "
            "Once the first target is hit, the stop trails "
            f"{breakout.trail_atr_multiple:g}x the {period}-period ATR behind the best price "
            f"the trade has seen, and never moves back past the entry price. That "
            f"ATR({period}) "
            f"is calculated from {minutes}-minute bars across trading sessions, using "
            "prior-session bars where they are available, so overnight gaps contribute to "
            f"true range. At least {breakout.trail_bars_min} completed {minutes}-minute "
            "bars "
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
        max_risk_row(cls, settings, "portfolio.py · enter"),
        Row(
            field="Min. R:R",
            value=f"{reward} {targets}",
            source="portfolio.py · on_filled_order",
        ),
        Row(
            field="Exit Rule",
            value="Scaled out in three: half the position as first filled at the first "
            "target, a quarter of it at the second, the remainder at the third. "
            "Partial short exits round down to whole shares and skip zero-share slices. Each slice "
            "of a long supports fractional shares. The resting stop still covers the position, "
            "and the next "
            "target or the closing deadline takes it. The trailing stop takes whatever is "
            "left if price turns first.",
            source="strategies/breakout.py · manage",
        ),
        Row(
            field="Emergency Exit",
            value=f"A market exit is submitted from {exit_at}, "
            f"{breakout.close_lead_minutes} minutes before the session close. "
            "The exchange calendar sets the close, including shortened sessions. "
            "The daily loss "
            "limit closes all positions and stops new entries for the rest of the day.",
            source="strategies/breakout.py · manage, portfolio.py · _emergency_exit",
        ),
    ]


def _daily_rows(cls: type[Daily], settings: RuleSettings, closes: datetime) -> list[Row]:
    prose = daily_prose(settings)[cls.key]
    period = settings.indicators.period
    average_sessions = settings.daily.average_sessions
    return [
        Row(field="Symbols", value=prose.symbols or symbols(settings), source=prose.symbols_source),
        Row(
            field="Market condition",
            value=f"The last completed close of {settings.benchmark_symbol} must be above its "
            f"{average_sessions}-day average. If it is not, no daily strategy takes a "
            "position that day.",
            source="strategies/daily.py · run",
        ),
        Row(field="Direction", value="Long only.", source="portfolio.py · enter"),
        Row(
            field="Range",
            value="Not used. This strategy reads daily bars and has no opening range.",
            source="strategies/daily.py · run",
        ),
        Row(field="Setup", value=prose.setup, source=prose.setup_source),
        Row(field="Confirmation", value=prose.confirmation, source=prose.setup_source),
        Row(
            field="Sorting",
            value="Ranked by the value traded in the last completed session, which is its "
            "close times its share volume, highest first. When more symbols qualify on the "
            "same morning than there is room to hold, the busiest take the slots. A symbol "
            "with no readable sessions is left out.",
            source="strategies/daily.py · _ranked",
        ),
        Row(
            field="Entry",
            value=prose.entry
            + (
                f" Earnings within {settings.earnings.block_days} days block an entry. "
                "A company with no earnings date on file can still be bought."
                if cls.does_heed_earnings
                else " Earnings do not block an entry."
            ),
            source=prose.entry_source,
        ),
        Row(
            field="Stop Loss",
            value=f"{cls.stop_atr_multiple:g}x the {period}-period ATR below the entry "
            f"price, then trailing {cls.stop_atr_multiple:g}x ATR below the highest close "
            "reached since entry. The stop only ever moves up.",
            source="strategies/daily.py · manage",
        ),
        max_risk_row(cls, settings, prose.risk_source),
        Row(
            field="Min. R:R",
            value="No fixed target. The trade is held while the trend holds and closed on "
            "the exit rule below.",
            source="strategies/daily.py · manage",
        ),
        Row(
            field="Exit Rule",
            value="An exit is submitted when the completed daily close falls below the stop, "
            "or when the close "
            f"drops below its {average_sessions}-day average, or RSI ({period}) falls under "
            f"{settings.daily.exit_rsi_max:g}. Any condition is sufficient.",
            source="strategies/daily.py · does_signal_exit",
        ),
        Row(
            field="Emergency Exit",
            value=(
                "Closed at the open of the last exchange session strictly before the company "
                "reports earnings, including weekend and holiday release dates. "
                "The daily loss limit closes all positions and "
                "stops new entries for the rest of the day."
                if cls.does_heed_earnings
                else "The daily loss limit closes all positions and stops new entries for "
                "the rest of the day. Earnings do not close a position for this strategy. "
                "It holds through the report and leaves on its stop or its exit rule."
            ),
            source="strategies/daily.py · manage, portfolio.py · _emergency_exit",
        ),
    ]
