"""Replay ORB5 over real 5-minute SIP bars, using the shipped rule functions.

Every decision below calls the same code the bot runs — orb_setup, session_volume,
entry_quantity, latest_atr, next_stop, fractional_allowed — so the backtest cannot
drift from the register. What is reimplemented here is only the *clock*: which
bars were visible at each scan, and what a market order would have paid.

Conservative choices, all stated so the result can be read honestly:
  - entry fills at the OPEN of the candle beginning at the scan boundary
  - when one bar spans both the stop and a target, the STOP is taken first
  - the 15:54 flatten is modelled as the close of the 15:50 candle
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, time
from math import isfinite

import pandas as pd


sys.path.insert(0, "/home/user/money-tree/src")

from bot.strategies.orb_base import (  # noqa: E402
    ORB_POSITIONS_MAX,
    ORB_RISK_CEILING,
    ORB_TURNOVER_MIN,
    orb_setup,
    session_volume,
)
from bot.strategies.shared import (  # noqa: E402
    entry_quantity,
    fractional_allowed,
    latest_atr,
    next_stop,
)


TZ = "America/New_York"
TARGETS = (1.5, 2.5, 4.0)
TRANCHES = (0.5, 0.25, 0.25)
SIGNAL_CANDLES_MAX = 2
VOLUME_MULTIPLE = 1.3
POSITION_FRACTION_MAX = 0.10
RISK_PER_DAY_MAX = 0.02
TRAIL_ATR_MULTIPLE = 1.5
TRAIL_BARS_MIN = 15
SCAN_FROM, SCAN_TO = time(9, 35), time(10, 30)
FLATTEN_AT = time(15, 50)


@dataclass
class Trade:
    session: date
    symbol: str
    direction: int
    entry_at: pd.Timestamp
    entry: float
    stop0: float
    risk: float
    quantity: float
    notional: float
    rvol: float
    range_pct: float
    stop_pct: float
    exit_at: pd.Timestamp | None = None
    pnl: float = 0.0
    r_multiple: float = 0.0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    stages: int = 0
    reason: str = ""
    ambiguous: bool = False


@dataclass
class Config:
    """Knobs the sweep varies. Defaults are exactly what ships."""

    volume_multiple: float = VOLUME_MULTIPLE
    targets: tuple[float, float, float] = TARGETS
    tranches: tuple[float, float, float] = TRANCHES
    stop_fraction_min: float | None = None  # None = use orb_setup's own band
    scale_out: bool = True
    breakeven_after_first: bool = True
    trail: bool = True
    positions_max: int = ORB_POSITIONS_MAX
    label: str = "shipped"


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    sessions: int = 0
    slots_from_beyond_top10: int = 0
    loss_limit_days: int = 0


def opening_range(session_bars: pd.DataFrame) -> tuple[float, float] | None:
    """High and low of the 09:30 candle — the register's five-minute range."""
    opening = session_bars.between_time("09:30", "09:34")
    if opening.empty:
        return None
    high, low = float(opening["high"].max()), float(opening["low"].min())
    return (high, low) if isfinite(high) and isfinite(low) and high > low else None


def first_break(after: pd.DataFrame, high: float, low: float) -> tuple[int, int, float] | None:
    """The FIRST candle since the range that closed outside it, per _orb_signal."""
    for position, value in enumerate(after["close"].tolist()):
        close = float(value)
        if not isfinite(close):
            continue
        if close > high:
            return position, 1, close
        if close < low:
            return position, -1, close
    return None


def manage(
    bars: pd.DataFrame,
    history: pd.DataFrame,
    trade: Trade,
    cfg: Config,
) -> Trade:
    """Walk the trade forward bar by bar under the register's exit rules."""
    d, entry, R = trade.direction, trade.entry, trade.risk
    targets = [entry + d * R * m for m in cfg.targets]
    stop = trade.stop0
    remaining = trade.quantity
    stage = 0
    realised = 0.0
    extreme = entry
    mfe = mae = 0.0

    for at, bar in bars.iterrows():
        hi, lo = float(bar["high"]), float(bar["low"])
        excursion = (hi - entry) / R if d == 1 else (entry - lo) / R
        adverse = (lo - entry) / R if d == 1 else (entry - hi) / R
        mfe, mae = max(mfe, excursion), min(mae, adverse)

        stop_hit = lo <= stop if d == 1 else hi >= stop
        target_hit = stage < 3 and (hi >= targets[stage] if d == 1 else lo <= targets[stage])
        if stop_hit and target_hit:
            trade.ambiguous = True

        # the stop is taken first when one bar spans both
        if stop_hit:
            realised += remaining * d * (stop - entry)
            trade.exit_at, trade.reason = at, "stopped" if stage == 0 else f"stop after T{stage}"
            remaining = 0.0
            break

        while stage < 3 and (hi >= targets[stage] if d == 1 else lo <= targets[stage]):
            share = trade.quantity * cfg.tranches[stage] if cfg.scale_out else trade.quantity
            share = min(share, remaining)
            realised += share * d * (targets[stage] - entry)
            remaining -= share
            stage += 1
            if not cfg.scale_out:
                break
        if remaining <= 1e-9:
            trade.exit_at, trade.reason = at, "all targets" if cfg.scale_out else "target"
            break

        if stage >= 1:
            if cfg.breakeven_after_first:
                stop = next_stop(d, stop, entry)
            if cfg.trail:
                extreme = max(extreme, hi) if d == 1 else min(extreme, lo)
                window = history[history.index <= at].between_time("09:30", "15:59")
                if len(window) >= TRAIL_BARS_MIN:
                    try:
                        trail = TRAIL_ATR_MULTIPLE * latest_atr(window)
                    except ValueError:
                        trail = 0.0
                    if trail > 0:
                        candidate = (
                            max(entry, extreme - trail) if d == 1 else min(entry, extreme + trail)
                        )
                        stop = next_stop(d, stop, candidate)

        if at.time() >= FLATTEN_AT:
            realised += remaining * d * (float(bar["close"]) - entry)
            trade.exit_at, trade.reason = at, "flat before close"
            remaining = 0.0
            break

    if remaining > 1e-9:
        last = bars.iloc[-1]
        realised += remaining * d * (float(last["close"]) - entry)
        trade.exit_at, trade.reason = bars.index[-1], "session end"

    trade.pnl = realised
    trade.r_multiple = realised / (trade.quantity * R) if trade.quantity * R else 0.0
    trade.mfe_r, trade.mae_r, trade.stages = mfe, mae, stage
    return trade


def replay(
    sessions: list[date],
    shortlist: dict[date, list[str]],
    bars: dict[str, pd.DataFrame],
    cfg: Config,
    equity0: float = 100_000.0,
) -> Result:
    """One session at a time, scanning on the five-minute boundary."""
    out = Result()
    equity = equity0
    for session in sessions:
        out.sessions += 1
        day_open_equity = equity
        ranked = shortlist.get(session, [])
        if not ranked:
            out.equity_curve.append((session, equity))
            continue

        # per-symbol session slices, prepared once
        day: dict[str, pd.DataFrame] = {}
        ranges: dict[str, tuple[float, float]] = {}
        for symbol in ranked:
            frame = bars.get(symbol)
            if frame is None:
                continue
            slice_ = frame[frame.index.normalize() == pd.Timestamp(session, tz=TZ)]
            if slice_.empty:
                continue
            rng = opening_range(slice_)
            if rng is None:
                continue
            day[symbol] = slice_
            ranges[symbol] = rng

        scanned: set[str] = set()
        traded: set[str] = set()
        open_trades: list[Trade] = []
        day_pnl = 0.0
        stopped_for_day = False

        clocks = pd.date_range(
            pd.Timestamp(f"{session} {SCAN_FROM}", tz=TZ),
            pd.Timestamp(f"{session} {SCAN_TO}", tz=TZ),
            freq="5min",
        )
        for now in clocks:
            if stopped_for_day or len(traded) >= cfg.positions_max:
                break
            candidates = []
            for rank, symbol in enumerate(ranked):
                if symbol in scanned or symbol in traded or symbol not in day:
                    continue
                frame = day[symbol]
                completed = frame[frame.index + pd.Timedelta(minutes=5) <= now]
                after = completed.between_time("09:35", "15:59")
                if after.empty:
                    continue
                high, low = ranges[symbol]
                signal = first_break(after, high, low)
                if signal is None:
                    continue
                position, direction, close = signal
                scanned.add(symbol)
                if len(after) - position > SIGNAL_CANDLES_MAX:
                    continue
                setup = orb_setup(high, low, close)
                if setup is None:
                    continue
                if (
                    cfg.stop_fraction_min is not None
                    and setup.risk / setup.close < cfg.stop_fraction_min
                ):
                    continue
                signal_at = after.index[position]
                window = bars[symbol]
                window = window[window.index <= signal_at]
                volume = session_volume(window, session, signal_at.time())
                if volume is None or volume.turnover < ORB_TURNOVER_MIN:
                    continue
                if volume.ratio < cfg.volume_multiple:
                    continue
                candidates.append((rank, symbol, setup, volume.ratio, high, low))

            for rank, symbol, setup, rvol, high, low in candidates:
                if len(traded) >= cfg.positions_max:
                    break
                fills = day[symbol][day[symbol].index >= now]
                if fills.empty:
                    continue
                price = float(fills.iloc[0]["open"])
                if not isfinite(price) or price <= 0:
                    continue
                d = setup.direction
                if d * (price - setup.stop) <= 0:
                    continue
                distance = abs(price - setup.stop)
                quantity = float(
                    entry_quantity(
                        equity,
                        price,
                        distance,
                        POSITION_FRACTION_MAX,
                        ORB_RISK_CEILING,
                        fractional_allowed(d, True),
                    )
                )
                if quantity <= 0:
                    continue
                if rank >= 10:
                    out.slots_from_beyond_top10 += 1
                trade = Trade(
                    session=session,
                    symbol=symbol,
                    direction=d,
                    entry_at=fills.index[0],
                    entry=price,
                    stop0=setup.stop,
                    risk=distance,
                    quantity=quantity,
                    notional=quantity * price,
                    rvol=rvol,
                    range_pct=100 * (high - low) / price,
                    stop_pct=100 * distance / price,
                )
                history = bars[symbol]
                trade = manage(fills, history, trade, cfg)
                traded.add(symbol)
                open_trades.append(trade)
                day_pnl += trade.pnl
                if day_pnl <= -RISK_PER_DAY_MAX * day_open_equity:
                    stopped_for_day = True
                    out.loss_limit_days += 1
                    break

        out.trades.extend(open_trades)
        equity += day_pnl
        out.equity_curve.append((session, equity))
    return out
