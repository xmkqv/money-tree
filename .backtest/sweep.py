"""Run the shipped configuration, then vary one lever at a time.

The point is not to find the best row — with a few hundred trades that would be
curve fitting — but to see whether ANY setting of the levers the register
actually exposes gets expectancy above zero, and how far off it is.
"""

import sys
from pathlib import Path

import pandas as pd


sys.path.insert(0, "/home/user/money-tree/.backtest")
from engine import Config, replay  # noqa: E402
from report import load, summarise  # noqa: E402


OUT = Path("/home/user/money-tree/.backtest")

CONFIGS = [
    Config(label="shipped (1.3x rvol, 1.5/2.5/4R, 50/25/25)"),
    # does the entry filter matter?
    Config(volume_multiple=1.0, label="rvol >= 1.0x"),
    Config(volume_multiple=2.0, label="rvol >= 2.0x"),
    Config(volume_multiple=3.0, label="rvol >= 3.0x"),
    # is the stop band doing anything on real ranges?
    Config(stop_fraction_min=0.015, label="stop >= 1.5% of price"),
    Config(stop_fraction_min=0.020, label="stop >= 2.0% of price"),
    # does the scale-out help or cap the winners?
    Config(scale_out=False, targets=(1.5, 1.5, 1.5), label="all out at 1.5R"),
    Config(scale_out=False, targets=(2.5, 2.5, 2.5), label="all out at 2.5R"),
    Config(scale_out=False, targets=(4.0, 4.0, 4.0), label="all out at 4R"),
    Config(targets=(1.0, 2.0, 3.0), label="closer targets 1/2/3R"),
    Config(targets=(2.0, 4.0, 8.0), label="wider targets 2/4/8R"),
    # is the trail earning its keep?
    Config(trail=False, label="no trail (fixed stop + targets)"),
    Config(trail=False, breakeven_after_first=False, label="no trail, no breakeven move"),
    # let the trend run: no scale-out, trail only
    Config(scale_out=False, targets=(99.0, 99.0, 99.0), label="trail only, no targets"),
]

if __name__ == "__main__":
    sessions, shortlist, bars = load()
    print(f"loaded {len(bars)} symbols, {len(sessions)} sessions\n", flush=True)
    rows = []
    for cfg in CONFIGS:
        result = replay(sessions, shortlist, bars, cfg)
        row = summarise(result, cfg.label)
        full = (
            sum(t * f for t, f in zip(cfg.targets, cfg.tranches, strict=True))
            if cfg.scale_out
            else cfg.targets[0]
        )
        row["breakeven_strike_%"] = round(100.0 / (1.0 + full), 1)
        rows.append(row)
        print(
            f"  {cfg.label:42} trades={row.get('trades', 0):4}  "
            f"E={row.get('expectancy_R', 0):+.3f}R  "
            f"win={row.get('win_rate_%', 0):5.1f}%  "
            f"need={row['breakeven_strike_%']:4.1f}%  "
            f"P&L=${row.get('pnl_$', 0):,.0f}",
            flush=True,
        )
        if cfg.label.startswith("shipped"):
            pd.DataFrame([t.__dict__ for t in result.trades]).to_parquet(
                OUT / "trades_base.parquet"
            )
            pd.DataFrame(result.equity_curve, columns=["session", "equity"]).to_parquet(
                OUT / "equity_base.parquet"
            )
    pd.DataFrame(rows).to_csv(OUT / "sweep.csv", index=False)
    print(f"\nwrote {OUT / 'sweep.csv'}")
