"""Check the replay's exit simulation against thirteen trades the bot really took.

The exits are the part of a backtest most able to flatter itself, so they are
measured against the fills Alpaca actually reported on 2026-08-31 and
2026-09-01. Each row is the real entry, the real initial stop, the real filled
quantity and the realised P&L; the harness is handed the first three and has to
arrive at the fourth from five-minute bars alone.

Known and expected divergences, all in a direction that can be reasoned about:

  ABEV  the live bot had no resting stop at all — the rounding bug PR #30 fixed
        — and exited at market a cent below its level, for -2R instead of -1R.
        The harness models the fixed code, so it is right to differ here.
  INFY  R was one cent. The live bot's +1.5R target was reached by a single
        tick and it scaled out; five-minute bars cannot resolve the sequencing
        of a move that small. The harness takes the stop, which is the
        conservative reading.
  PURR  the real stop filled one to three cents past its level. The harness
        fills at the level, so it is about 1-2% optimistic on slippage.
"""

import pickle
import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent))

from engine import Config, Trade, manage  # noqa: E402


# symbol, session, direction, entry, initial stop, filled quantity, entry clock, realised P&L
REAL = [
    ("PBR", "2026-08-31", 1, 19.44, 19.32, 505.505737, "09:42", -60.66),
    ("INFY", "2026-08-31", 1, 12.02, 12.01, 817.715189, "09:42", 4.09),
    ("ABEV", "2026-08-31", 1, 2.91, 2.90, 3382.024441, "09:42", -67.64),
    ("JBLU", "2026-08-31", -1, 4.64, 4.68, 2113.0, "09:46", -84.52),
    ("PCG", "2026-08-31", 1, 13.5626, 13.40, 721.659196, "10:00", -118.84),
    ("PURR", "2026-08-31", -1, 11.36, 11.66, 861.0, "10:00", -273.31),
    ("IREN", "2026-09-01", -1, 35.159315, 36.03, 277.0, "09:42", -243.95),
    ("OWL", "2026-09-01", 1, 11.97, 11.88, 816.177685, "09:46", -73.46),
    ("PFE", "2026-09-01", -1, 28.71, 28.84, 339.0, "09:50", -44.13),
    ("HL", "2026-09-01", 1, 19.32, 19.16, 504.962869, "09:50", 199.61),
    ("NIO", "2026-09-01", 1, 4.12, 4.06, 2366.245687, "10:00", -141.97),
    ("BTG", "2026-09-01", 1, 5.349322, 5.30, 1824.623948, "10:10", -89.99),
    ("KVUE", "2026-09-01", 1, 19.01, 18.98, 512.798527, "10:25", -15.38),
]
TOLERANCE_PCT = 5.0  # on the total, not per trade
EXPECTED_DIVERGENCE = {"ABEV", "INFY"}


def validate(bars: dict[str, pd.DataFrame]) -> int:
    cfg = Config()
    print(f"{'sym':6}{'actual$':>10}{'sim$':>10}{'diff$':>9}{'reason':>18}")
    actual_total = simulated_total = 0.0
    sign_matches = 0
    for symbol, day, direction, entry, stop, quantity, clock, actual in REAL:
        session = pd.Timestamp(day, tz="America/New_York")
        frame = bars[symbol]
        fills = frame[frame.index.normalize() == session].between_time(clock, "15:55")
        trade = Trade(
            session=session.date(),
            symbol=symbol,
            direction=direction,
            entry_at=fills.index[0],
            entry=entry,
            stop0=stop,
            risk=abs(entry - stop),
            quantity=quantity,
            notional=quantity * entry,
            rvol=0.0,
            range_pct=0.0,
            stop_pct=0.0,
        )
        trade = manage(fills, frame, trade, cfg)
        actual_total += actual
        simulated_total += trade.pnl
        if (trade.pnl > 0) == (actual > 0) or symbol in EXPECTED_DIVERGENCE:
            sign_matches += 1
        print(
            f"{symbol:6}{actual:10.2f}{trade.pnl:10.2f}{trade.pnl - actual:9.2f}{trade.reason:>18}"
        )
    drift = 100 * abs(simulated_total - actual_total) / abs(actual_total)
    print(
        f"\n{'TOTAL':6}{actual_total:10.2f}{simulated_total:10.2f}"
        f"{simulated_total - actual_total:9.2f}   drift {drift:.1f}%"
    )
    print(f"sign agreement: {sign_matches}/{len(REAL)}")
    ok = sign_matches == len(REAL) and drift <= TOLERANCE_PCT
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    stores = [Path(argument) for argument in sys.argv[1:]]
    if not stores:
        raise SystemExit("usage: validate.py <pickle of {symbol: 5-min frame}> [more...]")
    normalised: dict[str, pd.DataFrame] = {}
    for store in stores:
        with store.open("rb") as handle:
            raw = pickle.load(handle)
        for symbol, frame in raw.get("sip", raw).items():
            normalised[symbol] = frame.rename(
                columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
            )
    missing = sorted({row[0] for row in REAL} - set(normalised))
    if missing:
        raise SystemExit(f"no bars for {', '.join(missing)}")
    raise SystemExit(validate(normalised))
