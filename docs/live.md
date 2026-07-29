# Live data APIs

Systematic best-effort catalog of credible zero-cost live and near-live read APIs

Checked on 2026-07-28 against primary provider documentation

## Shape-compliant options

### Ranked starting points

| Need | First choice | Why |
| --- | --- | --- |
| US equity prototype | Alpaca IEX | Free RT WebSocket with clear feed identity |
| US consolidated quotes with brokerage | Tradier | RT consolidated equities and options |
| Broad asset prototype | Twelve Data | RT US equities, FX, and crypto on one schema |
| Crypto microstructure | Venue-native WebSockets | Lowest latency and fullest order-book semantics |
| Crypto cross-venue baseline | CoinGecko or CoinMarketCap | Normalized identifiers and one-minute snapshots |
| Filing catalysts | SEC EDGAR APIs plus latest-filings RSS | Official dissemination with measured sub-minute lag |
| Global news factors | GDELT | Broad multilingual NRT coverage with no key |
| US macro factors | Source agency plus FRED | Agency speed with FRED discovery and revision history |
| European macro factors | ECB plus Eurostat | SDMX access and delta-friendly queries |
| Entity normalization | OpenFIGI plus GLEIF | Instrument and legal-entity identifiers |

### Market and brokerage feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Alpaca Market Data](https://docs.alpaca.markets/docs/about-market-data-api) | US equities, options, crypto, news | REST and WebSocket JSON | RT IEX or D15 SIP on free plan | Key; 200 REST rpm, 1 stream, 30 equity symbols | Market-data agreement applies; display and onward use need entitlement review | Active; best free US equity event feed |
| [Finnhub](https://finnhub.io/pricing) | Stocks, FX, crypto, news, fundamentals | REST and WebSocket JSON | Provider marks free market and news updates RT | Key; 60 REST calls per minute and 50 WS symbols | Free use is limited by provider and exchange terms; no implied resale right | Active; broad prototype feed with generous symbol count |
| [Twelve Data](https://twelvedata.com/pricing) | US equities and ETFs, FX, crypto, reference, press releases | REST and trial WebSocket JSON | RT for listed free markets | Key; 8 credits per minute, 800 per day, 8 trial WS credits | Basic individual plan is personal, internal, and non-commercial | Active 2026; simplest multi-asset normalized schema |
| [Tradier Market Data](https://docs.tradier.com/docs/market-data) | US equities, options, indices, hourly Greeks | HTTPS and streaming JSON | RT consolidated in brokerage API; sandbox is D15 | Bearer token; brokerage account needed for RT; sandbox is free and delayed | Exchange agreements govern display and redistribution | Active; best for options with a Tradier account |
| [OANDA v20](https://developer.oanda.com/rest-live-v20/development-guide/) | FX, metals, and division-specific CFDs | REST JSON and chunked JSON pricing stream | RT tradable quotes; stream is capped at four prices per second per instrument | Practice or live account token; 120 REST rps, 20 streams, 2 new connections per second | Quotes are OANDA prices; terms and regional product rules apply | Mature active service; strong free practice FX stream |

#### Crypto venue feeds

Public market channels are normally free of API charges

They still inherit venue terms, market-data ownership, sanctions, and geography rules

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Binance Spot](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md) | Spot trades, books, tickers, candles | REST and WebSocket JSON or SBE | RT; stream speeds vary from 100 ms to 1 s | Public channels need no key; 5 inbound messages per second, 1024 streams per connection | Binance terms and regional availability apply; no blanket redistribution grant | Active 2026; deepest retail crypto spot feed in supported regions |
| [Coinbase Advanced Trade](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview) | Spot and supported derivatives, books, trades, candles | REST and WebSocket JSON | RT WebSocket; public REST has a 1 s cache by default | Most market channels need no JWT; channel-specific limits apply | Coinbase market-data terms apply; public access is not a resale license | Active; clean USD and regulated-venue features |
| [Kraken Spot](https://docs.kraken.com/api/docs/websocket-v2/ticker) | Spot books, trades, tickers, OHLC | REST and WebSocket v2 JSON | RT event stream | Public feed needs no key; public REST counters and pair-specific limits apply | Kraken terms apply; derived or displayed products need rights review | Active 2026; reliable sequence-aware spot feed |
| [OKX](https://www.okx.com/docs-v5/en/) | Spot, margin, futures, perpetuals, options | REST and WebSocket JSON | RT; channel push rates are documented per topic | Public channels need no key; 3 connection requests per second and 480 WS ops per hour | OKX terms and regional restrictions apply | Active with 2026 changelog; broad derivatives surface |
| [Bybit v5](https://bybit-exchange.github.io/docs/v5/ws/connect) | Spot, linear and inverse futures, options, spreads | REST and WebSocket JSON | RT; books down to 10 ms and tickers 50 to 100 ms | Public channels need no key; 500 connections per 5 minutes and 1000 market connections per IP | Bybit terms and jurisdiction rules apply | Active 2026; high-rate book and derivatives data |
| [Deribit](https://docs.deribit.com/) | Crypto options, futures, perpetuals, volatility indexes | JSON-RPC over WebSocket or HTTP, plus FIX | RT subscriptions | Public methods need no key; subscribe sustains about 3.3 requests per second with burst 10 | Deribit terms apply; index and market-data reuse needs review | Active 2026; first choice for crypto options surfaces |
| [Bitfinex v2](https://docs.bitfinex.com/docs/ws-public) | Spot and margin tickers, trades, books, candles, status | WebSocket JSON arrays and REST JSON | RT | No key; 20 new public connections per minute; docs conflict at 25 versus 30 subscriptions, so cap at 25 | Bitfinex terms apply; proprietary data cannot be assumed redistributable | Active; useful raw and aggregated order-book modes |
| [Gemini](https://developer.gemini.com/websocket/introduction) | Spot and supported derivatives, books, trades | REST and WebSocket JSON | RT low-latency public stream | Public read needs no key; 120 public REST requests per minute | Market Data Agreement applies; Gemini calls the data proprietary | Production docs updated in 2026; useful regulated spot venue |
| [KuCoin](https://www.kucoin.com/docs-new/websocket-api/base-info/introduction-uta) | Spot, margin, futures, options where available | REST and WebSocket JSON | RT | Pro public WS needs no token; 200 topics per connection and 100 client messages per 10 s | KuCoin terms and region-specific endpoints apply | Active 2026; broad altcoin coverage |
| [Gate API v4](https://www.gate.com/docs/developers/apiv4/ws/en/) | Spot and derivatives books, trades, tickers, candles | REST, WebSocket JSON, and SBE | RT trades; books can push at 100 ms | Public channels need no key; site docs list up to 900 public REST rps and 300 WS connections per IP | Gate terms and local-site restrictions apply | Active with 2026 changelog; useful altcoin and SBE feed |
| [Crypto.com Exchange](https://exchange-developer.crypto.com/exchange/v1) | Spot and derivatives tickers, trades, books, candles | REST and WebSocket JSON | RT | Public market methods need no key; per-method and per-IP limits apply | Exchange terms and geography rules apply | Active; useful secondary centralized venue |
| [Hyperliquid](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket) | On-chain perpetuals and spot, books, trades, mids, candles | REST POST and WebSocket JSON | RT by HyperCore block; book snapshots at least every 500 ms when active | No key for public data; 1200 REST weight per minute, 10 WS connections, 1000 subscriptions | Protocol and interface terms apply; blockchain facts remain independently verifiable | Active 2026; strongest free on-chain order-book stream |
| [dYdX Indexer](https://docs.dydx.xyz/) | dYdX Chain markets, books, trades, candles | REST and WebSocket JSON | RT indexer stream | Public data needs no key; deployment-specific rate limits apply | Open-source code does not waive interface or third-party data terms | Active; decentralized derivatives features |
| [Polymarket CLOB](https://docs.polymarket.com/developers/CLOB/websocket/market-channel) | Prediction-market books, prices, trades, tick sizes | REST and WebSocket JSON | RT market events | Market channel needs no auth; limits are not numerically published | Polymarket terms and regional restrictions apply | Active; event-probability and prediction-market signals |

### Normalized crypto and on-chain snapshots

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [CoinGecko Demo](https://docs.coingecko.com/docs/setting-up-your-api-key) | Coins, exchanges, market aggregates, metadata | REST JSON | Most market endpoints cache for about 60 s | Demo key; dashboard publishes the current minute and monthly allowance | Demo rights are limited; paid rights differ and redistribution is not implied | Active; strong normalized research baseline |
| [CoinMarketCap Basic](https://coinmarketcap.com/api/pricing/) | Coins, exchanges, rankings, market pairs, selected DEX data | REST JSON | 60 s update frequency on free Basic | Key or restricted keyless endpoint; 15,000 credits monthly and 50 rpm in current pricing | Current Basic pricing says commercial use; standalone resale remains barred | Active 2026; normalized IDs and broad asset metadata |
| [DefiLlama](https://defillama.com/docs/api) | DeFi TVL, protocols, chains, yields, stablecoins, prices | REST JSON | Route-dependent NRT snapshots | Public routes need no key; numeric free limit is not published | Attribute DefiLlama and inspect upstream protocol data rights | Active; best free DeFi state and TVL factors |

### News and release feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [GDELT 2.0](https://blog.gdeltproject.org/gdelt-3-0-coming-soon/) | Global multilingual news events, entities, tone, links | HTTP files, REST-like DOC and GEO APIs, CSV and JSON | NRT on a 15-minute heartbeat; some v3 products update each minute | No key; no fixed public quota, so cache and throttle | Article copyrights stay with publishers; GDELT metadata is not article ownership | Mature active feed; broad event and sentiment features |
| [Guardian Open Platform](https://open-platform.theguardian.com/access/) | Guardian articles, tags, sections, article text | REST JSON | New content appears after Guardian publication | Developer key; 1 call per second and 500 per day | Free only for non-commercial use; AI, mining, and commercial use need a license | Active; high-quality English news factors |
| [NewsAPI Developer](https://newsapi.org/pricing) | Headlines and article metadata from many publishers | REST JSON | Top headlines live, but article search is delayed 24 h | Key; 100 requests per day | Development and testing only; no staging, production, or full article rights | Active but not a free production feed |
| [SEC latest-filings RSS](https://www.sec.gov/about/rss-feeds) | New EDGAR filings and SEC publications | RSS and Atom XML | Closest free feed to RT filing availability | No key; SEC fair-access maximum is 10 requests per second across sec.gov | Public filings are accessible, but exhibits may retain third-party rights | Active; trigger ingestion before structured XBRL catches up |
| [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm) | Policy statements, speeches, press releases, enforcement | RSS XML | Release-driven | No key; no numeric quota, so conditional GET and polite polling | US government reuse rules apply; linked third-party material may differ | Active; policy-event triggers |
| [ECB RSS](https://www.ecb.europa.eu/home/html/rss.en.html) | Monetary policy, speeches, supervision, press releases | RSS XML | Release-driven | No key; no numeric quota published | ECB copyright and attribution rules apply | Active; euro policy-event triggers |

### Official macro and regulatory APIs

These feeds are live relative to their publication cadence

They are not tick feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [FRED and ALFRED](https://fred.stlouisfed.org/docs/api/fred/overview.html) | US and global macro series, releases, vintages | REST XML or JSON | Release-driven; aggregator lag varies by source | Free key; exact cap is unpublished and enforced with HTTP 429 | Third-party series can be copyrighted; required FRED notice applies | Active; discovery, revisions, and common macro joins |
| [BLS Public Data](https://www.bls.gov/developers/api_FAQs.htm) | CPI, PPI, payrolls, employment, wages, productivity | REST JSON and XLSX | Release-driven | v1 no key at 25 queries per day; v2 key at 500 per day; both 50 requests per 10 s | US government data is generally reusable with attribution and no endorsement | Active; ingest directly at labor and inflation releases |
| [BEA](https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf) | GDP, income, trade in value added, regional and industry accounts | REST JSON or XML | Release-driven | Free key; adaptive per-minute quota returns 429 and Retry-After | US government reuse rules apply | Active with 2026 guide; national accounts and revisions |
| [Census Data API](https://www.census.gov/data/developers/guidance/api-user-guide.html) | Trade, population, business, housing, surveys | REST JSON | Dataset and release dependent | Key optional for light use; key is required above 500 queries per IP per day | Cite Census; some datasets have their own notes | Active 2026; trade and economic-demographic factors |
| [EIA Open Data v2](https://www.eia.gov/opendata/documentation.php) | Oil, gas, power, coal, renewables, prices, inventories | REST JSON or XML | Constant updates; weekly inventory APIs can lag release by up to 2 h | Free key; stay below about 5 rps and 9000 per hour; 5000 JSON rows per response | Attribution requested; do not falsely represent modified data as EIA | Active v2.1.12 in 2026; energy supply and inventory factors |
| [Treasury Fiscal Data](https://fiscaldata.treasury.gov/api-documentation/) | US debt, auctions, rates, receipts, outlays, securities | REST JSON, CSV, and XML | Dataset and release dependent | No key; no fixed public quota, so paginate and cache | US government reuse rules and dataset notes apply | Active; sovereign funding and fiscal-liquidity features |
| [Federal Reserve Data Download Program](https://www.federalreserve.gov/datadownload/) | Rates, industrial production, money, bank assets, FX | Parameterized HTTP downloads in CSV, XML, or Excel | Release-driven | No key; no numeric quota published | US government reuse rules apply | Active; direct source for selected Fed statistical releases |
| [ECB Data Portal](https://data.ecb.europa.eu/help/api/overview) | Rates, FX, money, credit, markets, balance sheets, macro | SDMX 2.1 REST in XML, JSON, or CSV | Release-driven with `updatedAfter` delta queries | No key; numeric rate cap is not published | ECB copyright, attribution, and no-endorsement rules apply | Active; euro rates and revision-aware ingestion |
| [Eurostat](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction) | EU macro, prices, trade, labor, industry, population | REST SDMX 2.1 or 3.0, JSON-stat, CSV, TSV, XML | Database refreshes at 11:00 and 23:00 CET | No key and free; use async API for large queries | Eurostat reuse policy normally permits reuse with source acknowledgement | Active; broad European panels and trade data |
| [ONS](https://developer.ons.gov.uk/) | UK economy, prices, labor, population, trade | REST JSON and CSV downloads | Release-driven | No key for public data; 120 requests per 10 s and 200 per minute | Open Government Licence applies unless a dataset says otherwise | Active; UK macro at source |
| [OECD Data Explorer](https://www.oecd.org/en/data/insights/data-explainers/2024/11/Api-best-practices-and-recommendations.html) | Cross-country macro, leading indicators, trade, tax, labor | SDMX REST in CSV, JSON, and XML | Mostly release-driven; a few high-frequency indicators | No key; 60 data downloads per hour; VPN traffic is blocked | OECD terms and dataset source rights apply | Active 2026 but rate constrained; normalized country panels |
| [IMF Data API](https://data.imf.org/en/Resource-Pages/IMF-API) | IFS and other IMF macro, financial, fiscal, and external datasets | SDMX 2.1 and 3.0 REST | Release-driven | Free beta portal account currently required for API exploration | IMF terms and dataset-specific source notes apply | Active beta portal; external-sector and cross-country macro |
| [World Bank Indicators](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation) | Development, macro, finance, population, climate indicators | REST JSON or XML | Dataset dependent, usually low frequency | No key; no fixed quota is published | CC BY 4.0 applies to many Bank datasets, with source exceptions | Mature active service; slow-moving structural factors |
| [Bank of England IADB](https://www.bankofengland.co.uk/boeapps/database/Help.asp) | UK rates, SONIA, FX, money, credit, securities, balance sheets | Parameterized HTTP XML, CSV, or HTML | Release or daily cadence | No key; up to 300 series codes per request | Bank terms apply; FX series are explicitly not official market rates | Mature active service; UK rates and lending features |
| [CFTC Public Reporting](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) | Commitments of Traders and other public market reports | Socrata REST, OData, JSON, and CSV | Weekly or report-specific release cadence | No key for normal public calls; Socrata throttles anonymous heavy use | US government reuse rules and report definitions apply | Active 2026; positioning and crowding factors |

### Filings, fundamentals, and reference data

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [SEC EDGAR data APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Submission history, 10-K and 10-Q facts, 8-K, 20-F, 6-K, frames | REST JSON plus bulk ZIP | Submissions typically under 1 s; XBRL typically under 1 min | No key; identify the client and remain at or below 10 requests per second | Filing access is public; exhibits and third-party content can keep copyright | Active; official live fundamentals and filing events |
| [OpenFIGI v3](https://www.openfigi.com/api/documentation) | FIGI mapping, instrument search, exchange and security metadata | REST JSON | Reference updates rather than market ticks | No key at 25 mappings per minute and 5 searches per minute; free key raises limits | Open Symbology license applies; third-party identifiers are withheld by design | Active v3; normalize instruments before joins |
| [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api) | LEIs, legal entities, parents, children, BIC and ISIN mappings | REST JSON:API | Golden Copy updates and record events | No key; numeric quota is not prominently published | LEI data is open under GLEIF terms with attribution | Active production; issuer and counterparty identity |
| [Companies House](https://developer.company-information.service.gov.uk/) | UK companies, officers, filings, charges, insolvency | REST JSON and streaming API for changed resources | NRT for register changes; filing document timing varies | API key; 600 requests per 5 minutes | Crown and third-party rights vary by field and document | Active; UK company events and issuer reference |

### Free-looking services that are not free live production feeds

| API | Coverage | Transport and format | Freshness | Free limits and auth | Rights and redistribution | Status and best use |
| --- | --- | --- | --- | --- | --- | --- |
| [Massive Stocks Basic](https://massive.com/pricing?product=stocks) | US stocks and reference data | REST JSON and daily files | EOD on free plan; D15 begins on paid Starter | Key; 5 calls per minute on free Stocks Basic | Free plan is individual use; business and redistribution need separate rights | Active; historical bootstrap only |
| [Alpha Vantage](https://www.alphavantage.co/support/) | Stocks, FX, crypto, indicators, news, fundamentals | REST JSON or CSV | Free US stock data is neither RT nor D15; both are premium | Key; 25 requests per day | Provider terms apply and licensed US quote use needs paid entitlement | Active; low-rate research and non-US-stock snapshots |
| [Financial Modeling Prep Basic](https://site.financialmodelingprep.com/pricing-plans) | US profiles, reference, historical data, selected fundamentals | REST JSON | EOD on free Basic | Key; 250 calls per day and 500 MB trailing 30-day bandwidth | Personal use only; display and redistribution require an agreement | Active Stable API; reference and EOD bootstrap |
| [NewsAPI Developer](https://newsapi.org/pricing) | News metadata and headlines | REST JSON | Search articles delayed 24 h; top headlines may be live | Key; 100 requests per day | Development only with no production use | Active; evaluation only |
| [Tradier Sandbox](https://docs.tradier.com/docs/endpoints) | US equities and options plus paper trading | REST and streaming JSON | D15 | Sandbox bearer token | Sandbox and exchange terms apply | Active; integration tests before a brokerage account |
| [OANDA Practice](https://developer.oanda.com/rest-live-v20/development-guide/) | Simulated FX and CFD account with current OANDA quotes | REST and chunked JSON | RT quotes in a non-production account | Free practice account token | Quotes remain subject to OANDA terms | Active; realistic FX pipeline tests |

## Other

### Scope

`Every` means every credible service found through a category-by-category search

A service qualifies when it has all of these properties

- An official or clearly maintained API
- A non-zero no-cost allowance, demo environment, or public read channel
- Data useful to financial forecasting, risk, or trading
- Documented access that does not depend on scraping a website

Free does not imply real-time, production rights, redistribution rights, or an SLA

Latency labels used below

| Label | Meaning |
| --- | --- |
| `RT` | Event-driven or provider-described real-time data |
| `NRT` | Near-real-time data, normally one minute or less |
| `D15` | At least 15 minutes delayed |
| `release` | Updated around an official scheduled or unscheduled release |
| `EOD` | End-of-day only |
| `trial` | A test surface or restricted symbol set, not a durable live tier |

Limits change often

Read the linked plan, rate-limit, and rights pages before production use

### Selection rules

1. Prefer the venue-native stream for execution-time features
2. Prefer the issuing agency for scheduled macro releases
3. Add an aggregator for discovery, symbology, and cross-source normalization
4. Record the named feed, not only the vendor
5. Reject any source whose free rights conflict with the intended deployment
6. Treat a trial, sandbox, and free production tier as different products
7. Benchmark observed lag because provider labels are not latency guarantees

### Loader contract

Every live adapter should preserve these fields before any tensor conversion

```python:exemplar:live-envelope
{
    "source": "provider-and-feed",
    "instrument": "provider-native-id",
    "event_time": "provider timestamp",
    "received_time": "local monotonic and UTC timestamp",
    "sequence": "provider sequence or null",
    "latency_class": "RT | NRT | D15 | release | EOD | trial",
    "entitlement": "public | key | account | trial",
    "payload": "unaltered provider record",
}
```

Also retain these states

- Snapshot, delta, correction, cancellation, and heartbeat
- Reconnect count and gap detection result
- Provider timezone and trading calendar
- Upstream revision or vintage identifier
- License class and display or redistribution restriction

This makes dlt ingestion idempotent and prevents delayed data from entering an RT feature set

### Operational cautions

- A WebSocket is transport, not a guarantee of real-time source data
- Free US equities often expose IEX only, D15 SIP, or EOD data
- Crypto feeds need snapshot-plus-delta recovery and sequence-gap handling
- Official macro values can be revised after first release
- News metadata does not grant rights to copy full articles
- Public exchange channels can disappear by jurisdiction without a code change
- Free-plan terms can forbid commercial, shared, display, or model-training use
- No free service in this catalog should be treated as an execution-grade SLA

### Source maintenance

Review this file at least quarterly

Recheck pricing, limits, market entitlements, geography, and API changelogs before each release

The fastest-changing rows are Alpaca, Finnhub, Twelve Data, crypto venues, and aggregators
