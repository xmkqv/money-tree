# Feeds

Live data feeds for the `data` concern's acquisition and delivery mechanism. These sit outside
money-tree's interfaces, per the `operation` layer's `composition is external`

The adopted shape, per [README](../README.md): `grain(dlt(source))`. pfeed is its live edge; dlt and
Grain acquire in batch and do not appear below

Checked on 2026-08-06

| Library | Kind | Language | Last activity | Lock-in | Free | Price |
| --- | --- | --- | --- | --- | --- | --- |
| [pfeed](https://github.com/PFund-Software-Ltd/pfeed) | Loader | Python | 2026-07-22, v0.0.19 | Low — 9+ sources, open, self-hostable | Yes | Free |
| [qldata](https://pypi.org/project/qldata/) | Loader | Python | Stale — 2025-12-05, v0.3.0 | Medium — crypto only (Binance, Bybit) | Yes (MIT) | Free |
| [n-ashare-market](https://pypi.org/project/n-ashare-market/) | Loader | Python | 2026-08-05, v0.5.30 | High — China A-share only, private GitLab | Unclear — undeclared license | Unclear |
| [flint-trading](https://github.com/sohan-shingade/flint) | Loader | Python | 2026-04-07, v1.1.0, single release | Medium — Drift/Hyperliquid plus ccxt | Yes (MIT) | Free |
| [finda](https://github.com/kshlgrg/finda) | Loader | Python | Stale — 2025-12-28, v2.0.0 | Low — wraps ccxt, alpaca-py, dukascopy | Yes (MIT) | Free |
| [cryptofeed](https://github.com/bmoscon/cryptofeed) + [cryptostore](https://github.com/bmoscon/cryptostore) | Loader | Python | **Archived 2026-07-07** | Low — 30+ crypto exchanges, but dead | Yes (XFree86, BSD-style) | Free |
| [NautilusTrader adapters](https://github.com/nautechsystems/nautilus_trader/tree/develop/crates/adapters) | Engine feed | Rust + Python | 2026-08-02, v1.231.0 | High — emits engine types, not standalone. 18 adapters: Binance, Bybit, Coinbase, Kraken, OKX, Deribit, BitMEX, dYdX, Hyperliquid, Lighter, Derive, IB, Databento, Tardis, Polymarket, Betfair, Architect, on-chain | Yes (LGPL-3.0) | Free |
| [Lumibot data_sources](https://github.com/Lumiwealth/lumibot/tree/dev/lumibot/data_sources) | Engine feed | Python | 2026-08-05, v4.5.83 | Medium — 13 sources: Alpaca, IB, Tradier, Schwab, Tradovate, ProjectX, Databento, Polygon, Polymarket, Bitunix, ccxt, Alpha Vantage, Yahoo | GPL-3.0 repo; PyPI metadata says MIT | Free |
| [QuantConnect LEAN](https://github.com/QuantConnect/Lean) | Engine feed | C# + Python | Push 2026-08-06; untagged since 2017 | High — feed bound to engine; brokerage and `Lean.DataSource.*` integrations, count unverified | Yes (Apache-2.0 engine) | Free self-host; cloud plans paid |
| [Freqtrade](https://github.com/freqtrade/freqtrade) | Engine feed | Python | 2026-07-31, calendar release | Low — feed is ccxt, listed separately below; crypto only | Yes (GPL-3.0) | Free |
| [Backtrader stores](https://github.com/mementum/backtrader/tree/master/backtrader/stores) | Engine feed | Python | Stale — HEAD 2024-08-19, PyPI 1.9.78.123 2023-04-19 | Medium — 3 live stores: IB, OANDA, VisualChart | Yes (GPL-3.0) | Free |
| [Databento](https://github.com/databento/databento-python) | Vendor SDK | Python | 2026-08-05, v0.83.0 | High — single vendor | Client free | Data usage-based, paid |
| [Alpaca-py](https://github.com/alpacahq/alpaca-py) | Vendor SDK | Python | 2026-07-02, v0.43.5 | High — single vendor | Client free (Apache-2.0) | Free data tier plus paid tiers |
| [Polygon / Massive client-python](https://github.com/polygon-io/client-python) | Vendor SDK | Python | Stale — no release since 2025-10-30 | High — single vendor | Client free (MIT) | Data subscription, paid |
| [Tardis.dev](https://pypi.org/project/tardis-dev/) | Vendor SDK | Python | 2026-07-03, v4.2.1 | High — single vendor | No | Paid, usage-based |
| [ThetaDataDx](https://github.com/userFRM/ThetaDataDx) | Vendor SDK | Rust, Python, TS, C++ | 2026-07-31, v0.3.0 | High — single vendor | Client free (Apache-2.0) | Data subscription, paid |
| [lse-data](https://github.com/londonstrategicedge/lse-data) | Vendor SDK | Python | 2026-07-07, v0.14.0 | High — single vendor | Client MIT | Unclear — vendor data terms apply |
| [0xArchive](https://github.com/0xArchiveIO) | Vendor SDK | TS, Python, Rust SDKs plus CLI | 8 repos, all pushed 2026-08-06 | High — 2 crypto venues, realtime plus replay | Clients MIT | Service pricing unverified |
| [ib_async](https://pypi.org/project/ib-async/) | Vendor SDK | Python | 2025-12-08, v2.1.0 | High — single broker, needs a running TWS or IB Gateway | Client free | Free with an IBKR account |
| [ccxt](https://github.com/ccxt/ccxt) | Aggregator | JS, Python, PHP, others | Near-daily releases, v4.5.71 | Low — 100+ exchanges | Yes (MIT) | Free; CCXT Pro paid |
| [barter-data](https://github.com/barter-rs/barter-rs) | Aggregator | Rust | 2026-03-05, v0.11.0; workspace push 2026-06-06 | Low — standalone crate, no engine adoption; crypto only | Yes (MIT) | Free |
| [OpenBB Platform](https://github.com/OpenBB-finance/OpenBB) | Aggregator | Python | 2026-05-26, v4.7.2 | Low — 30+ providers; live is provider-dependent | Yes (AGPL-3.0) | Free; some providers need their own paid keys |
| [DBN](https://github.com/databento/dbn) | Codec | Rust + Python, C++ | 2026-08-04, v0.65.0 | Medium — Databento's own encoding, binary over TCP | Yes (Apache-2.0) | Codec free; data metered per message |
| [simple-binary-encoding](https://github.com/real-logic/simple-binary-encoding) | Codec | Java, C++, C# | 2026-07-03, v1.39.0 | None — FIX standard, schema-driven | Yes (Apache-2.0) | Free |
| [Binance SBE](https://developers.binance.com/docs/binance-spot-api-docs/sbe-market-data-streams) | Codec | Schema plus [C++ sample](https://github.com/binance/binance-sbe-cpp-sample-app) | Sample app push 2026-07-30, untagged | Medium — venue-specific schema; SBE frames, JSON subscribe | Yes | Free |
| ITCH 5.0 toolkit — SoupBinTCP, MoldUDP64, TCP | Codec | Rust | 2026-05, **repo URL unpinned** | Low — ITCH 5.0 only; real transports, not just files | Unverified | Free |
| [QuickFIX](https://github.com/quickfix/quickfix) | FIX | C++, with Python and Ruby bindings | 2026-05-09, v1.16.0 | None — FIX 4.x and 5.0 standard, full session layer | Custom QuickFIX license, BSD-style | Free |
| [quickfix-go](https://github.com/quickfixgo/quickfix) | FIX | Go | v0.9.10 2025-08-08, push 2026-07-31 | None — FIX standard, full session layer | Custom, BSD-style | Free |
| [PyKX](https://github.com/KxSystems/pykx) | Store | Python wrapper over proprietary q | 2026-06-24, v4.0.0 | High — proprietary `q.so` binary | Wrapper free; q proprietary | Paid enterprise license; limited personal edition |
| [websocat](https://github.com/vi/websocat) | Shell | Rust | v1.14.1 2025-12-27, push 2026-07-26 | None — netcat for `ws://` | Yes (MIT/Apache-2.0) | Free |
| [dbn CLI](https://github.com/databento/dbn/blob/main/rust/dbn-cli/README.md) | Shell | Rust | 2026-08-04, v0.65.0 | Medium — DBN input only; streams to CSV, JSON lines | Yes (Apache-2.0) | Free |
| [tickrs](https://github.com/tarkah/tickrs) | Shell | Rust | v0.15.0 2025-12-15, push 2026-05-19 | High — Yahoo Finance only, TUI refresh | Yes (MIT) | Free |
| [ticker](https://github.com/achannarasappa/ticker) | Shell | Go | 2026-06-21, v5.3.0 | High — Yahoo Finance only, TUI refresh | Yes (GPL-3.0) | Free |

ib_async is the maintained successor to ib_insync and implements the IB protocol internally with no
`ibapi` dependency, but it still requires a running TWS or IB Gateway, and that is a GUI process —
it does not deploy headlessly without extra scaffolding

curl cannot open a WebSocket, so websocat is the gap-filler for every `wss://` feed above

[tickstream](https://tick-stream.xyz/) quotes CME tick and options from $19/mo and
[iTick](https://itick.org/en) advertises comparable rates. Neither is verifiable against an
independent source, and both sit two orders below the CME license fee in
[Entitlement costs](#entitlement-costs)

## Entitlement costs

The vendor subscription is rarely the cost; the exchange license fee is, and the
professional and non-display classifications set it

| Feed | Non-professional | Professional, non-display | Notes |
| --- | --- | --- | --- |
| Crypto public WS — Binance, Coinbase, Kraken | Free | Free | No license regime; Binance caps 1,024 streams per connection and 300 connections per IP per 5 minutes |
| [Alpaca](https://alpaca.markets/data) Basic | Free | Free | Real-time equities are **IEX only**, roughly 2-3% of consolidated volume |
| Alpaca Algo Trader Plus | $99/mo | $99/mo | Full SIP plus OPRA options, to 10,000 rpm |
| [Polygon / Massive](https://massive.com/pricing) | $29 to $399/mo by tier | Same | Developer $99, Advanced $199, All-Access $399; polygon.io/pricing now redirects to Massive |
| [Databento](https://databento.com/pricing) Standard | $199/mo | $199/mo | Plus historical from ~$0.50/GB; $125 free credits per new team, 6-month expiry |
| CME via Databento | $36.50/mo license plus $32.65/mo | **$1,219/mo** license plus metered | License fees passed through with no upcharge; delayed CME data is $304/mo; reflects the [2026-06-22 increase](https://databento.com/blog/updates-to-subscription-pricing) |
| [Nasdaq TotalView-ITCH](https://www.nasdaqtrader.com/content/ProductsServices/PriceList/Nasdaq_US_Equities_Price_List_2025_2026_2027.pdf) direct | Not applicable | **$500/mo per subscriber** at 1-39 | Then $20,000/firm at 40-99, $40,000 at 100-249, $100,000 at 250+ |

Two classifications decide the bill, and exchanges audit both

- Professional versus non-professional turns on trading own money, no firm affiliation, and no
  business use — on CME the same feed is $36.50 or $1,219, a 33x swing
- Display versus non-display turns on whether a human reads the data or an algorithm consumes it,
  which makes **any automated trading system non-display by definition**

## Other

None of the alternatives displace pfeed as the live edge of the locked pipe. Vendor SDKs trade
generality for lock-in; engine feeds emit engine types and are not consumable without the engine
around them; the other loaders are each narrower than pfeed on scope, freshness, or stack

The raw layer does not displace it either, but it bounds `live`. A binary codec is a source that
dlt acquires, never a replacement for it, and the entitlement table is the real constraint on
which venues `live(data_config, source)` can ever reach: crypto is free and unmetered, US
equities are affordable, and CME or Nasdaq depth is a four-figure monthly commitment before a
line of code runs
