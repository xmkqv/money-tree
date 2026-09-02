"""Pull daily bars for every tradable, fractionable US equity over the window."""

import sys
import time
from pathlib import Path

import pandas as pd
import requests


sys.path.insert(0, "/home/user/money-tree/src")

from bot.config import settings  # noqa: E402


# The project's settings object resolves the credentials whatever case the
# environment spells them in, so the fetchers read them the same way the bot does.
assert settings.alpaca_api_key and settings.alpaca_api_secret
H = {
    "APCA-API-KEY-ID": settings.alpaca_api_key.get_secret_value(),
    "APCA-API-SECRET-KEY": settings.alpaca_api_secret.get_secret_value(),
}
OUT = Path("/home/user/money-tree/.backtest")
OUT.mkdir(exist_ok=True)
START, END = "2024-08-01", "2026-09-01"

r = requests.get(
    "https://paper-api.alpaca.markets/v2/assets",
    headers=H,
    params={"status": "active", "asset_class": "us_equity"},
    timeout=180,
)
syms = sorted(
    {
        a["symbol"]
        for a in r.json()
        if a.get("tradable")
        and a.get("fractionable")
        and "/" not in a["symbol"]
        and a.get("exchange") in ("NASDAQ", "NYSE", "ARCA", "AMEX")
    }
)
print(f"candidate symbols: {len(syms)}", flush=True)

rows = []
batch = 200
for i in range(0, len(syms), batch):
    chunk = syms[i : i + batch]
    tok = None
    got = 0
    while True:
        p = {
            "symbols": ",".join(chunk),
            "timeframe": "1Day",
            "start": START,
            "end": END,
            "limit": 10000,
            "adjustment": "all",
            "feed": "sip",
        }
        if tok:
            p["page_token"] = tok
        for attempt in range(5):
            try:
                resp = requests.get(
                    "https://data.alpaca.markets/v2/stocks/bars", headers=H, params=p, timeout=180
                )
                if resp.status_code == 200:
                    break
                time.sleep(2**attempt)
            except Exception:
                time.sleep(2**attempt)
        else:
            print("FAILED chunk", i, flush=True)
            break
        j = resp.json()
        for sym, bars in (j.get("bars") or {}).items():
            for b in bars:
                rows.append((sym, b["t"], b["o"], b["h"], b["l"], b["c"], b["v"]))
                got += 1
        tok = j.get("next_page_token")
        if not tok:
            break
    print(f"  {i + len(chunk)}/{len(syms)} rows={len(rows):,}", flush=True)

df = pd.DataFrame(rows, columns=["symbol", "t", "open", "high", "low", "close", "volume"])
df["t"] = pd.to_datetime(df["t"], format="ISO8601", utc=True).dt.tz_convert("America/New_York")
df["session"] = df["t"].dt.normalize()
df.to_parquet(OUT / "daily.parquet", index=False)
print(f"saved {len(df):,} daily bars for {df.symbol.nunique():,} symbols", flush=True)
