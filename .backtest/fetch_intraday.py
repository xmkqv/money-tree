"""Five-minute SIP bars for every shortlisted symbol across the window."""

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
START, END = "2024-08-01", "2026-08-28"

syms = [s.strip() for s in (OUT / "symbols.csv").read_text().split("\n") if s.strip()]
print(f"symbols: {len(syms)}", flush=True)
done_dir = OUT / "intraday"
done_dir.mkdir(exist_ok=True)

batch = 40
for i in range(0, len(syms), batch):
    chunk = syms[i : i + batch]
    part = done_dir / f"part_{i:04d}.parquet"
    if part.exists():
        print(f"  skip {i}", flush=True)
        continue
    rows = []
    tok = None
    while True:
        p = {
            "symbols": ",".join(chunk),
            "timeframe": "5Min",
            "start": START,
            "end": END,
            "limit": 10000,
            "adjustment": "all",
            "feed": "sip",
        }
        if tok:
            p["page_token"] = tok
        for attempt in range(6):
            try:
                resp = requests.get(
                    "https://data.alpaca.markets/v2/stocks/bars", headers=H, params=p, timeout=300
                )
                if resp.status_code == 200:
                    break
                time.sleep(min(2**attempt, 30))
            except Exception:
                time.sleep(min(2**attempt, 30))
        else:
            print(f"  FAILED {i}", flush=True)
            break
        j = resp.json()
        for sym, bars in (j.get("bars") or {}).items():
            for b in bars:
                rows.append((sym, b["t"], b["o"], b["h"], b["l"], b["c"], b["v"]))
        tok = j.get("next_page_token")
        if not tok:
            break
    df = pd.DataFrame(rows, columns=["symbol", "t", "open", "high", "low", "close", "volume"])
    df.to_parquet(part, index=False)
    print(f"  {i + len(chunk)}/{len(syms)} part rows={len(df):,}", flush=True)
print("done", flush=True)
