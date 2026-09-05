from datetime import date, datetime, timedelta
from typing import Any, TypedDict

from bot.strategies.daily_base import (
    DAILY_EARNINGS_EXIT_LEAD_MINUTES,
    DAILY_EXITS_BEFORE_EARNINGS,
    DAILY_STOP_ATR_MULTIPLES,
)
from bot.strategies.orb_base import (
    ORB_CLOSE_LEAD_MINUTES,
    ORB_ENTRY_EXTENSION_MAX,
    ORB_HISTORY_SESSIONS,
    ORB_OPENING_MINUTES,
    ORB_POSITIONS_MAX,
    ORB_PRICE_USD_MIN,
    ORB_RANGE_FRACTION_MIN,
    ORB_RISK_MAX,
    ORB_SCAN_MINUTES,
    ORB_SIGNAL_CANDLES_MAX,
    ORB_STOP_FRACTION_MAX,
    ORB_STOP_FRACTION_MIN,
    ORB_TARGET_MULTIPLES,
    ORB_TRAIL_ATR_MULTIPLE,
    ORB_TRAIL_BARS_MIN,
    ORB_TURNOVER_USD_MIN,
    ORB_VOLUME_MULTIPLES,
)
from bot.strategies.shared import NOTIONAL_USD_MIN, PERIOD, upcoming_session_bounds
from bot.strategies.tfb_50 import (
    TFB_POSITIONS_MAX,
    TFB_PRICE_USD_MIN,
    TFB_RISK_MAX,
    TFB_TURNOVER_SESSIONS,
    TFB_TURNOVER_USD_MIN,
)
from bot.types import (
    POSITION_FRACTION_CAP_MAX,
    POSITIONS_MAX,
    STRATEGY_LABELS,
    StrategyName,
    TradingConfiguration,
)

from .ledger import label_order


class Row(TypedDict):
    field: str
    value: str
    source: str


class StrategyCard(TypedDict):
    id: str
    short: str
    label: str
    kind: str
    rows: list[Row]


FIELDS = [
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
]
UNIVERSE_CAP_USD_MIN = 500_000_000.0
STRATEGY_SHORT_LABELS: dict[StrategyName, str] = {
    "orb": "ORB5",
    "orb_momentum": "ORB10",
    "sma": "Momentum SMA",
    "tfb_50": "TFB-50",
}
STRATEGY_KINDS: dict[StrategyName, str] = {
    "orb": "Intraday breakout",
    "orb_momentum": "Intraday breakout",
    "sma": "Daily trend",
    "tfb_50": "Daily trend",
}


def entry_windows() -> dict[str, dict[str, str]]:
    opens, closes = upcoming_session_bounds(date.today())
    scan_end = opens + timedelta(minutes=ORB_SCAN_MINUTES)
    windows = {
        strategy: (opens + timedelta(minutes=minutes), scan_end)
        for strategy, minutes in ORB_OPENING_MINUTES.items()
    }
    windows.update({strategy: (opens, closes) for strategy in DAILY_STOP_ATR_MULTIPLES})
    return {
        strategy: {"from": f"{window[0]:%H:%M}", "to": f"{window[1]:%H:%M}"}
        for strategy, window in windows.items()
    }


def strategy_spec(configuration: TradingConfiguration, *, configured: bool) -> dict[str, Any]:
    per_trade = configuration.risk_per_trade_max
    daily_loss = configuration.risk_per_day_max
    opens, closes = upcoming_session_bounds(date.today())

    cards = [
        StrategyCard(
            id=strategy,
            short=STRATEGY_SHORT_LABELS[strategy],
            label=STRATEGY_LABELS[strategy],
            kind=STRATEGY_KINDS[strategy],
            rows=(
                _orb(strategy, per_trade, opens, closes)
                if strategy in ORB_OPENING_MINUTES
                else _daily(strategy, per_trade, closes)
            ),
        )
        # Listed by the short label, the same order the rest of the site uses.
        for strategy in sorted(
            STRATEGY_SHORT_LABELS, key=lambda name: label_order(STRATEGY_SHORT_LABELS[name])
        )
    ]
    return {
        "fields": FIELDS,
        "strategies": cards,
        "portfolio": portfolio_rules(daily_loss),
        "configured": configured,
    }


def portfolio_rules(daily_loss: float) -> list[Row]:
    return [
        Row(
            field="Position cap",
            value=f"At most {POSITIONS_MAX} positions open at once, counting orders already "
            "placed but not yet filled.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="Breakout cap",
            value=f"At most {ORB_POSITIONS_MAX} breakout positions open at once across both "
            "intraday strategies. Every breakout is the same bet on the same half hour, so "
            "the two strategies share one allowance rather than each taking their own.",
            source="portfolio.py · _orb_position_count",
        ),
        Row(
            field="Exposure",
            value="The total value held never exceeds account equity, so the account never "
            "trades on borrowed money.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="One owner per stock",
            value="Only one strategy holds a given stock at a time; the others skip it while "
            "that position is open.",
            source="portfolio.py · _is_claimed",
        ),
        Row(
            field="Daily loss limit",
            value=f"If equity falls {_pct(daily_loss)} below the previous close, every position "
            "is closed and no new trade is opened until the next session.",
            source="portfolio.py · _is_daily_loss_reached",
        ),
    ]


def _millions(value: float) -> str:
    return f"${value / 1_000_000:g}M"


def _pct(fraction: float) -> str:
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


UNIVERSE = (
    f"US equities screened daily: market cap {_millions(UNIVERSE_CAP_USD_MIN)} or more, share "
    f"price ${ORB_PRICE_USD_MIN:.0f} or more, 3-month average daily turnover "
    f"{_millions(ORB_TURNOVER_USD_MIN)} or more, and tradable and fractionable at Alpaca."
)

TFB_UNIVERSE = (
    f"{UNIVERSE} This strategy then screens that list again on its own floors: share price "
    f"${TFB_PRICE_USD_MIN:.0f} or more, and turnover averaging "
    f"{_millions(TFB_TURNOVER_USD_MIN)} or "
    f"more across the last {TFB_TURNOVER_SESSIONS} completed sessions — the value actually "
    "traded, not a share count against today's price. A symbol whose sessions cannot be read "
    "does not pass."
)


def _orb(strategy: StrategyName, per_trade: float, opens: datetime, closes: datetime) -> list[Row]:
    minutes = ORB_OPENING_MINUTES[strategy]
    volume_multiple = ORB_VOLUME_MULTIPLES[strategy]
    target_multiples = ORB_TARGET_MULTIPLES[strategy]
    entry_extension_max = ORB_ENTRY_EXTENSION_MAX[strategy]
    risk_cap = ORB_RISK_MAX if strategy == "orb" else per_trade
    opening_end = f"{opens + timedelta(minutes=minutes):%H:%M}"
    first_entry = f"{opens + timedelta(minutes=2 * minutes):%H:%M}"
    scan_end = f"{opens + timedelta(minutes=ORB_SCAN_MINUTES):%H:%M}"
    exit_at = f"{closes - timedelta(minutes=ORB_CLOSE_LEAD_MINUTES):%H:%M}"
    exit_before = f"{closes - timedelta(minutes=ORB_CLOSE_LEAD_MINUTES - 1):%H:%M}"

    confirmation = (
        f"Volume traded up to the signal candle's close is at least {volume_multiple:g}x the "
        f"{ORB_HISTORY_SESSIONS}-session average at the same time of day, and that average "
        f"session turns over at least {_millions(ORB_TURNOVER_USD_MIN)}. "
        f"All {ORB_HISTORY_SESSIONS} earlier sessions "
        "must be there to compare against — a shorter history is not a weaker signal, it is "
        "no confirmation at all, and the breakout is passed over. The reading is taken as the "
        "signal candle closed rather than as the scan runs, so a breakout read a pass late is "
        "still confirmed on the moment that made it. Each session is measured between its own "
        "opening and closing bell, so a half day is compared as a half day."
    )

    first, second, third = target_multiples
    multiples = f"{first:g}x, {second:g}x and {third:g}x"
    reward = f"{first:g}:1 at the first target, then {second:g}:1 and {third:g}:1."
    targets = (
        f"Targets are re-cut from the filled price: {multiples} the risk actually taken, so a "
        "fill away from the signal price carries them with it. Cut from the opening range "
        "instead, a breakout candle closing well past the level filled above targets already "
        "counted as reached and scaled the trade out on the spot."
    )

    extension = (
        ""
        if entry_extension_max is None
        else f" It is also passed over if that live quote sits more than "
        f"{_pct(entry_extension_max)} of the opening range beyond the breakout level: the stop "
        "is a fixed distance inside the range, so a price further past it risks more for the "
        "same setup while leaving less of the move to collect."
    )

    return [
        Row(field="Market", value=UNIVERSE, source="portfolio.py · _discover_eligible_symbols"),
        Row(
            field="Sentiment",
            value="None. This strategy takes signals whatever the wider market is doing.",
            source="portfolio.py · _run_orb",
        ),
        Row(
            field="Direction",
            value="Long and short. A short is skipped when the broker will not lend the stock, "
            "and is sized in whole shares — a broker lends shares, not fractions of one, so "
            "every order on a short leg is rounded down to a whole number. Longs use "
            "fractional quantities when the account allows them.",
            source="portfolio.py · _enter, _protect, _exit",
        ),
        Row(
            field="Range",
            value=f"The opening range is the first {minutes}-minute candle: the opening bell up "
            f"to {opening_end}, the last trade before {opening_end} being the one that closes "
            "it. Its high and low set the levels for the day. The bell is read from the "
            "exchange calendar, so a late open moves the range with it.",
            source="portfolio.py · _run_orb, strategies/shared.py · session_bounds",
        ),
        Row(
            field="Setup",
            value=f"The first completed {minutes}-minute candle since the range that closes above "
            "the range high (long) or below the range low (short) — a candle still forming never "
            f"signals. Checked every {minutes} minutes from {opening_end}, the moment the opening "
            f"candle closes, to {scan_end}, at most once per stock per day. The whole session "
            "since the range is re-read on every pass rather than only its newest candle, so a "
            "breakout whose bars reached the scan late is still the candle the signal is taken "
            f"from — but only while it is one of the last {ORB_SIGNAL_CANDLES_MAX} completed "
            f"candles, {ORB_SIGNAL_CANDLES_MAX * minutes} minutes of the move. A close further "
            "back than that has already run, and is passed over rather than chased. "
            "Once either breakout strategy has traded a stock, both leave it alone for the rest "
            f"of the session. The range itself must be at least {_pct(ORB_RANGE_FRACTION_MIN)} of "
            f"the price, and the stop cut from it between {_pct(ORB_STOP_FRACTION_MIN)} and "
            f"{_pct(ORB_STOP_FRACTION_MAX)} of the price — a narrower range puts the stop inside "
            "the spread, where the next tick decides the trade.",
            source="portfolio.py · _run_orb, orb_base.py · is_orb_setup_ready",
        ),
        Row(field="Confirmation", value=confirmation, source="portfolio.py · _orb_confirm"),
        Row(
            field="Sorting",
            value="Ranked by the value traded in the last completed daily session — its close "
            "times its share volume — highest first. When more breakouts fire than there "
            "is room to hold, the busiest take the slots. This is a different question "
            "from the confirmation above, which measures each stock against its own "
            "history rather than against other stocks.",
            source="portfolio.py · _rank_candidates",
        ),
        Row(
            field="Entry",
            value="A market order goes in the moment the scan reads the breakout, filling at the "
            "next executable price — the open of the next "
            f"{minutes}-minute candle when the signal is read on its own boundary, {first_entry} "
            "at the earliest, "
            "since the opening candle cannot break its own range. Good for the day only. The "
            "size is worked out from the live quote, falling back to the breakout candle's "
            "close, and the fill then sets the entry, the risk and the targets. It is passed "
            "over if another strategy already holds the stock, if the account is at its position "
            "cap or fully invested, if the size that fits the risk limits comes to less than "
            f"${NOTIONAL_USD_MIN:.0f}, or if that live quote has already run back through the "
            "stop the breakout would have been given — a position cannot be opened already "
            f"past its own exit.{extension}",
            source="portfolio.py · on_trading_iteration, _run_orb, _enter",
        ),
        Row(
            field="Stop Loss",
            value="Three quarters of the way back into the opening range for a long, a quarter "
            "for a short. Once the first target is hit the stop trails "
            f"{ORB_TRAIL_ATR_MULTIPLE:g}x the {PERIOD}-period ATR behind the best price the "
            "trade has seen, and never moves back "
            f"past the entry price. That ATR({PERIOD}) is calculated from {minutes}-minute "
            "candles across trading sessions, using available prior-session bars as needed, so "
            f"overnight gaps contribute to true range. At least {ORB_TRAIL_BARS_MIN} completed "
            f"{minutes}-minute candles must be available; because prior sessions are included, "
            "this requirement will normally already be satisfied when the trade begins. "
            "The level rests as a live order at "
            "the broker, replaced whenever it moves and re-sent if it ever stops covering the "
            "whole position. A level the market has already reached cannot rest as an order, so "
            "when the stop lands at or beyond the last price the whole position is closed at "
            "market there and then instead. The move to breakeven after the first target is the "
            "usual way this happens: price back at the entry is the stop being hit, and the "
            "position leaves at market rather than waiting for an order that could not be placed.",
            source="portfolio.py · _run_orb, _manage_orb, _protect, _resync_stops",
        ),
        Row(
            field="Max Risk",
            value=f"{_pct(risk_cap)} of account equity per trade"
            + (
                f" — this strategy states its own {_pct(ORB_RISK_MAX)} in the register, so "
                f"that governs instead of the configured {_pct(per_trade)}."
                if strategy == "orb"
                else " (the configured per-trade limit; this strategy states none of its own)."
            )
            + f" A single position is never worth more than {_pct(POSITION_FRACTION_CAP_MAX)} "
            "of equity.",
            source="portfolio.py · _enter",
        ),
        Row(field="Min. R:R", value=f"{reward} {targets}", source="portfolio.py · on_filled_order"),
        Row(
            field="Exit Rule",
            value="Scaled out in three: half the position as first filled at the first target, "
            "a quarter of it at the second, the remainder at the third. On a short each slice "
            "is rounded down to whole shares, and one worth less than a single share is "
            "skipped rather than sent — the resting stop still covers the position, and the "
            "next target or the closing deadline takes it. The trailing stop takes whatever "
            "is left if price turns first.",
            source="portfolio.py · _manage_orb",
        ),
        Row(
            field="Emergency Exit",
            value=f"Everything is closed before {exit_before} — the exit is sent at {exit_at}, "
            f"{ORB_CLOSE_LEAD_MINUTES} minutes before the closing bell the exchange calendar "
            "gives for the session, so the market order fills in time and a half day closes on "
            "its own clock. This strategy never holds overnight. The daily loss limit closes all "
            "positions and stops new entries for the rest of the day.",
            source="portfolio.py · _manage, _is_daily_loss_reached",
        ),
    ]


def _daily(strategy: StrategyName, per_trade: float, closes: datetime) -> list[Row]:
    stop_multiple = DAILY_STOP_ATR_MULTIPLES[strategy]
    earnings_exit = f"{closes - timedelta(minutes=DAILY_EARNINGS_EXIT_LEAD_MINUTES):%H:%M}"
    if strategy == "sma":
        setup = (
            "The closing price crosses back above its 20-day average while the trend is "
            "already stacked underneath it: price above the 50-day average, and that "
            "average above the 200-day. Needs 200 sessions of history."
        )
        confirmation = f"RSI ({PERIOD}) at 50 or above, and ADX ({PERIOD}) at 25 or above."
        entry = (
            "A three-day structure: one session closes below the 20-day average, the next "
            "closes back above it and higher than that first close, and the buy goes in at "
            "the open of the third. Market buy, retried every iteration until the close. "
            "Skipped if "
            "the company reports earnings within 5 days. A company with no earnings date on "
            "file is not held back; one whose calendar cannot be read at all is left for "
            "that session."
        )
        risk = (
            "No per-trade risk limit is set for this strategy, so the size comes from the "
            f"position cap alone: never more than {_pct(POSITION_FRACTION_CAP_MAX)} of equity."
        )
        setup_source = "strategies/shared.py · does_momentum_enter"
        entry_source = "strategies/shared.py · does_momentum_enter, portfolio.py · _run_sma"
    else:
        setup = (
            "The closing price is above its 50-day average, that average is higher than it "
            "was 3 sessions ago, and the close beats the previous session's high."
        )
        confirmation = f"ADX ({PERIOD}) at 20 or above."
        entry = (
            "Market buy at the open, then retried every iteration until the close. The "
            "setup is cut from completed sessions, so the day's list is scanned once and "
            "re-offered: a name that could not be funded at the open — no slot left, no "
            "affordable size, another strategy holding it — is taken later in the day if "
            "one frees up. Upcoming earnings do not block an entry for this strategy."
        )
        risk = (
            f"{_pct(TFB_RISK_MAX)} of account equity per trade — this strategy states its "
            f"own {_pct(TFB_RISK_MAX)} in the register, so that governs instead of the "
            f"configured {_pct(per_trade)}. A single position is never worth more than "
            f"{_pct(POSITION_FRACTION_CAP_MAX)} of equity, and this strategy holds at most "
            f"{TFB_POSITIONS_MAX} positions at once."
        )
        setup_source = "strategies/shared.py · does_tfb_enter"
        entry_source = "portfolio.py · _run_tfb"

    return [
        Row(
            field="Market",
            value=TFB_UNIVERSE if strategy == "tfb_50" else UNIVERSE,
            source="portfolio.py · _discover_eligible_symbols"
            + (", strategies/tfb_50.py · is_tfb_market_ready" if strategy == "tfb_50" else ""),
        ),
        Row(
            field="Sentiment",
            value="The S&P 500 must be trading above its own 20-day average. If it is not, no "
            "daily strategy takes a position that day.",
            source="portfolio.py · _run_daily",
        ),
        Row(field="Direction", value="Long only.", source="portfolio.py · _enter"),
        Row(
            field="Range",
            value="Not used. This strategy reads daily candles and has no opening range.",
            source="portfolio.py · _run_daily",
        ),
        Row(field="Setup", value=setup, source=setup_source),
        Row(field="Confirmation", value=confirmation, source=setup_source),
        Row(
            field="Sorting",
            value="Ranked by the value traded in the last completed session — its close times "
            "its share volume — highest first. When more symbols qualify on the same "
            "morning than there is room to hold, the busiest take the slots. A symbol "
            "whose session cannot be read ranks last but still trades.",
            source="portfolio.py · _ranked",
        ),
        Row(field="Entry", value=entry, source=entry_source),
        Row(
            field="Stop Loss",
            value=f"{stop_multiple:g}x the {PERIOD}-period ATR below the entry price, then "
            f"trailing {stop_multiple:g}x ATR below the highest close reached since entry. The "
            "stop only ever moves up.",
            source="portfolio.py · _manage_daily",
        ),
        Row(
            field="Max Risk",
            value=risk,
            source="portfolio.py · _run_tfb, _enter"
            if strategy == "tfb_50"
            else "portfolio.py · _enter",
        ),
        Row(
            field="Min. R:R",
            value="No fixed target. The trade is held while the trend holds and closed on the "
            "exit rule below, so no reward-to-risk ratio is set in advance.",
            source="portfolio.py · _manage_daily",
        ),
        Row(
            field="Exit Rule",
            value="Closed when the price falls through the trailing stop, or when the close "
            f"drops below its 20-day average, or RSI ({PERIOD}) falls under 50. Either "
            "one is enough on its own.",
            source="strategies/shared.py · does_signal_exit",
        ),
        Row(
            field="Emergency Exit",
            value=(
                f"Closed {DAILY_EARNINGS_EXIT_LEAD_MINUTES} minutes before the closing bell "
                f"({earnings_exit} on a full session) on the session before the company "
                "reports earnings, unless that calendar cannot be read, in which case the "
                "position is left alone. The daily loss limit closes all positions and stops "
                "new entries for the rest of the day."
                if DAILY_EXITS_BEFORE_EARNINGS[strategy]
                else "The daily loss limit closes all positions and stops new entries for "
                "the rest of the day. Earnings do not close a position for this strategy — it "
                "holds through the report and leaves on its threshold or its exit rule."
            ),
            source="portfolio.py · _manage_daily, _is_daily_loss_reached",
        ),
    ]
