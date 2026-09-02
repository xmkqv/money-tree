"""Per-session eligible universe, and the shortlist ranked the way the bot ranks.

The register screens on market cap, share price and 3-month average turnover.
Market cap needs the Yahoo screen, which this environment cannot reach, so the
$500M cap floor is not applied — turnover and price are, from the same daily
bars the ranking reads. That makes the universe here slightly WIDER than the
bot's, never narrower, so a setup the bot would have taken cannot be missed.

The bot ranks candidates by the previous session's traded value and fills three
slots, so only the top of that ranking can ever trade. The shortlist keeps the
top SHORTLIST_DEPTH names per session; how often a slot is filled from beyond
the top ten is reported so the depth can be shown to be enough.
"""

from pathlib import Path

import pandas as pd


OUT = Path("/home/user/money-tree/.backtest")
PRICE_MIN = 5.0
TURNOVER_MIN = 20_000_000.0
HISTORY_SESSIONS = 60  # a trading quarter, for the "3-month average"
SHORTLIST_DEPTH = 40

daily = pd.read_parquet(OUT / "daily.parquet")
daily = daily.sort_values(["symbol", "session"])
daily["turnover"] = daily["close"] * daily["volume"]

g = daily.groupby("symbol", sort=False)
daily["avg_turnover"] = g["turnover"].transform(
    lambda s: s.rolling(HISTORY_SESSIONS, min_periods=HISTORY_SESSIONS).mean().shift(1)
)
daily["prev_close"] = g["close"].transform(lambda s: s.shift(1))
daily["prev_traded"] = g["turnover"].transform(lambda s: s.shift(1))

eligible = daily[
    (daily["avg_turnover"] >= TURNOVER_MIN)
    & (daily["prev_close"] >= PRICE_MIN)
    & daily["prev_traded"].notna()
].copy()
print(f"eligible symbol-sessions: {len(eligible):,}")

eligible["rank"] = eligible.groupby("session")["prev_traded"].rank(ascending=False, method="first")
short = eligible[eligible["rank"] <= SHORTLIST_DEPTH].sort_values(["session", "rank"])
short[["session", "symbol", "rank", "prev_traded", "prev_close"]].to_parquet(
    OUT / "shortlist.parquet", index=False
)

per_day = eligible.groupby("session").size()
print(
    f"sessions: {per_day.size}  |  eligible names per session: "
    f"median {per_day.median():.0f}, min {per_day.min()}, max {per_day.max()}"
)
print(f"shortlist rows: {len(short):,}  |  unique symbols: {short.symbol.nunique():,}")
pd.Series(sorted(short.symbol.unique())).to_csv(OUT / "symbols.csv", index=False, header=False)
