"""Run the replay and print what the register needs to be judged on."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd


sys.path.insert(0, "/home/user/money-tree/.backtest")
from engine import Config, Result, replay  # noqa: E402


OUT = Path("/home/user/money-tree/.backtest")
TZ = "America/New_York"


def load() -> tuple[list[date], dict[date, list[str]], dict[str, pd.DataFrame]]:
    short = pd.read_parquet(OUT / "shortlist.parquet")
    short["session"] = pd.to_datetime(short["session"]).dt.date
    shortlist = {
        session: list(group.sort_values("rank")["symbol"])
        for session, group in short.groupby("session")
    }
    parts = sorted((OUT / "intraday").glob("part_*.parquet"))
    frames = [pd.read_parquet(p) for p in parts]
    raw = pd.concat(frames, ignore_index=True)
    raw["t"] = pd.to_datetime(raw["t"], format="ISO8601", utc=True).dt.tz_convert(TZ)
    raw = raw.sort_values(["symbol", "t"])
    bars = {
        symbol: group.set_index("t")[["open", "high", "low", "close", "volume"]]
        for symbol, group in raw.groupby("symbol", sort=False)
    }
    sessions = sorted(shortlist)
    return sessions, shortlist, bars


def summarise(result: Result, label: str, equity0: float = 100_000.0) -> dict[str, object]:
    trades = result.trades
    if not trades:
        return {"config": label, "trades": 0}
    df = pd.DataFrame([t.__dict__ for t in trades])
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]
    r = df["r_multiple"]
    curve = pd.Series([e for _, e in result.equity_curve])
    drawdown = ((curve - curve.cummax()) / curve.cummax()).min() * 100
    full = df[df["stages"] >= 3]
    return {
        "config": label,
        "trades": len(df),
        "sessions": result.sessions,
        "trades_per_session": round(len(df) / max(result.sessions, 1), 2),
        "win_rate_%": round(100 * len(wins) / len(df), 1),
        "full_winners_%": round(100 * len(full) / len(df), 1),
        "expectancy_R": round(r.mean(), 3),
        "total_R": round(r.sum(), 1),
        "avg_win_R": round(wins["r_multiple"].mean(), 2) if len(wins) else 0.0,
        "avg_loss_R": round(losses["r_multiple"].mean(), 2) if len(losses) else 0.0,
        "pnl_$": round(df["pnl"].sum(), 0),
        "return_%": round(100 * df["pnl"].sum() / equity0, 2),
        "max_dd_%": round(drawdown, 2),
        "reached_1.5R_%": round(100 * (df["mfe_r"] >= 1.5).mean(), 1),
        "reached_2.5R_%": round(100 * (df["mfe_r"] >= 2.5).mean(), 1),
        "reached_4R_%": round(100 * (df["mfe_r"] >= 4.0).mean(), 1),
        "ambiguous_bars_%": round(100 * df["ambiguous"].mean(), 1),
        "avg_risk_$": round((df["quantity"] * df["risk"]).mean(), 0),
        "risk_spread_x": round(
            (df["quantity"] * df["risk"]).max() / max((df["quantity"] * df["risk"]).min(), 1e-9), 1
        ),
        "slots_beyond_top10": result.slots_from_beyond_top10,
        "loss_limit_days": result.loss_limit_days,
    }


def breakeven_strike(targets: tuple[float, ...], tranches: tuple[float, ...]) -> float:
    full = sum(t * f for t, f in zip(targets, tranches, strict=True))
    return 100.0 / (1.0 + full)


if __name__ == "__main__":
    sessions, shortlist, bars = load()
    print(f"loaded {len(bars)} symbols, {len(sessions)} sessions", flush=True)
    base = Config()
    result = replay(sessions, shortlist, bars, base)
    row = summarise(result, base.label)
    for key, value in row.items():
        print(f"  {key:24} {value}")
    full = sum(t * f for t, f in zip(base.targets, base.tranches, strict=True))
    print(
        f"\n  full winner pays {full:.3f}R -> break-even strike "
        f"{breakeven_strike(base.targets, base.tranches):.1f}%"
    )
    pd.DataFrame([t.__dict__ for t in result.trades]).to_parquet(OUT / "trades_base.parquet")
    pd.DataFrame(result.equity_curve, columns=["session", "equity"]).to_parquet(
        OUT / "equity_base.parquet"
    )
