# Traders

Research checked on 2026-07-28

## Shape-compliant options

### Decision

Implement one broker adapter first and keep the contract venue-neutral

Use Alpaca paper trading for the fastest US-equity integration

Use IBKR as the breadth and production-control benchmark

Use venue-native APIs for production crypto and CCXT only for discovery or portability

Choose a live broker only after residency, instruments, tax wrapper, and costs are known

### Securities and multi-asset brokers

| API | Assets | Interface | Test mode | Access and limits | Best fit |
| --- | --- | --- | --- | --- | --- |
| [Alpaca Trading API](https://docs.alpaca.markets/docs/trading-api) | US stocks, options, crypto | REST and WebSocket | Free paper account | Live eligibility varies | Fast first adapter |
| [IBKR APIs](https://ibkrcampus.com/api) | Global multi-asset | Web, WebSocket, TCP, FIX | Funded clients get paper | Data subscriptions and sessions apply | Broad production broker |
| [Tradier Brokerage API](https://docs.tradier.com/docs/getting-started) | US stocks and options | REST and streaming | Sandbox | Account and market-data terms apply | Simple US options |
| [Schwab Trader API](https://developer.schwab.com/products/trader-api--individual) | US securities | REST and streaming | No equivalent full simulator assumed | Approved Schwab account and app | Existing Schwab users |
| [tastytrade Open API](https://developer.tastytrade.com/) | Stocks, options, futures, crypto | REST and streaming | Sandbox | Account and product approval apply | Multi-leg options |
| [TradeStation API](https://api.tradestation.com/docs/) | Stocks, options, futures | REST and HTTP streams | SIM mirrors live API | Brokerage approval applies | US multi-asset |
| [Saxo OpenAPI](https://www.developer.saxo/openapi/learn/welcome) | Global multi-asset | REST and streaming | Simulation account | Regional entity and product rules | European multi-asset |
| [Trading 212 Public API](https://docs.trading212.com/api/) | Invest and Stocks ISA | REST | Demo endpoint | Beta and limited account types | UK retail equities |
| [cTrader Open API](https://help.ctrader.com/open-api/) | Broker-dependent FX and CFDs | TCP or WebSocket, JSON or Protobuf | Demo | 50 non-history requests per second | cTrader brokers |
| [IG Labs](https://labs.ig.com/) | CFDs, spread bets, options, FX | REST and streaming | Demo account | Quotas and regional products apply | UK leveraged markets |
| [OANDA v20](https://developer.oanda.com/rest-live-v20/introduction/) | FX and CFDs by region | REST and stream | Practice account | Entity and instrument limits apply | FX automation |
| [Tradovate API](https://api-d.tradovate.com/) | Futures | REST and WebSocket | Demo | API and market-data terms apply | Retail futures |
| [MetaTrader 5 Python](https://www.mql5.com/en/docs/python_metatrader5) | Broker-dependent | Local terminal bridge | Broker demo | Requires terminal and supported broker | Existing MT5 setup |

#### Alpaca

Alpaca paper trading is globally available with email registration

Its official documentation describes free paper trading with real-time simulation data

The simple REST and WebSocket model is the shortest path to a complete adapter

Watch US-only equity scope, data-feed entitlements, and paper-fill optimism

#### Interactive Brokers

IBKR offers the widest instrument and venue coverage in this catalog

The Web API exposes HTTP and WebSocket access

The TWS API uses an asynchronous TCP socket with an official Python client

Retail Web API clients require a local Java gateway

One username can have only one active brokerage session

Paper accounts are attached to approved and funded live accounts

Market-data subscriptions are separate and user-specific

IBKR should be the contract stress test even when it is not the first integration

#### tastytrade

The official API exposes balances, positions, market data, orders, and complex options

Its sandbox and multi-leg order support make it a strong derivatives candidate

Confirm instrument approval and real-time data terms before implementation

#### TradeStation

TradeStation provides one interface for stocks, options, and futures

Its simulator uses the same API shape but instant simulated fills

Treat those fills as functional tests rather than execution evidence

#### European and UK choices

Saxo offers the broadest multi-asset OpenAPI in this group

Trading 212 has an official beta API for Invest and Stocks ISA accounts

cTrader and IG focus on broker-dependent leveraged products

OANDA is the narrowest clean choice for supported FX and CFD accounts

Product legality and protections differ materially by regional entity

### Crypto exchanges

| API | Products | Interface | Test mode | Access notes | Best fit |
| --- | --- | --- | --- | --- | --- |
| [Coinbase Advanced Trade](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview) | Spot | REST and WebSocket | Limited sandbox behavior | Account and region required | Regulated retail spot |
| [Coinbase Exchange](https://docs.cdp.coinbase.com/exchange/introduction/welcome) | Spot | REST, WebSocket, FIX | Sandbox | Exchange account required | Higher-volume spot |
| [Kraken](https://docs.kraken.com/) | Spot and futures by entity | REST, WebSocket, FIX | Beta environment varies | Product access varies | Strong native API |
| [Gemini](https://developer.gemini.com/docs/docs) | Spot and supported derivatives | REST and WebSocket | Full sandbox | Account and region required | Clear sandbox |
| [Binance](https://developers.binance.com/en/docs/introduction) | Spot and derivatives by entity | REST, WebSocket, FIX or SBE | Testnets by product | Strong regional restrictions | Deep product surface |
| [OKX](https://www.okx.com/docs-v5/en/) | Spot, futures, swaps, options | REST and WebSocket | Demo trading | Domain and products vary by region | Unified crypto API |
| [Bybit V5](https://bybit-exchange.github.io/docs/v5/intro) | Spot, derivatives, options | REST and WebSocket | Testnet | US and other restrictions apply | Unified derivatives API |
| [Deribit](https://docs.deribit.com/) | Crypto options and futures | JSON-RPC over HTTP or WebSocket | Test environment | Account and region required | Crypto options |
| [Hyperliquid](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api) | Perpetuals and spot | REST and WebSocket | Testnet | Wallet signing and region rules | On-chain execution |

#### Native API rule

Use a venue-native API for order placement, reconciliation, and private streams

Native APIs expose exchange-specific order flags and error states first

Use [CCXT](https://github.com/ccxt/ccxt) for market discovery and low-risk prototypes

Do not assume CCXT gives identical order semantics across exchanges

#### Crypto safety

- Bind API keys to fixed IPs where supported
- Disable withdrawal permission
- Use separate subaccounts per strategy
- Reconcile fills from private streams and REST
- Handle exchange sequence gaps explicitly
- Enforce price, notional, leverage, and position caps locally
- Store decimal quantities without binary rounding
- Check the correct regional API domain at startup

### Prediction markets

| API | Interface | Test mode | Access notes | Best fit |
| --- | --- | --- | --- | --- |
| [Kalshi](https://docs.kalshi.com/welcome) | REST and WebSocket | Demo | Membership and jurisdiction rules | Regulated event contracts |
| [Polymarket CLOB](https://docs.polymarket.com/developers/CLOB/introduction) | REST, WebSocket, signed orders | No full simulator assumed | Wallet, funding, and geoblocking | On-chain prediction markets |

Kalshi publishes OpenAPI and AsyncAPI specifications

Polymarket requires careful wallet signing and jurisdiction checks

Event markets need settlement and contract-definition validation beyond normal symbol mapping

### Selection matrix

| Need | First candidate | Challenger |
| --- | --- | --- |
| Fast US equity paper path | Alpaca | TradeStation |
| Global multi-asset | IBKR | Saxo |
| US options | tastytrade | Tradier or IBKR |
| UK ISA equities | Trading 212 beta | Broker availability check |
| Retail futures | Tradovate | IBKR or TradeStation |
| FX | OANDA | cTrader or IG |
| Regulated crypto spot | Coinbase | Kraken or Gemini |
| Crypto options | Deribit | Bybit by region |
| Prediction markets | Kalshi | Polymarket by jurisdiction |

### Recommendation

Start with Alpaca paper when US equities are acceptable

Start with IBKR paper when global or derivatives breadth is already required

Keep crypto adapters native and venue-scoped

Treat regional eligibility and market-data entitlements as deployment configuration

## Other

### Scope

This catalog covers official execution APIs available to individual developers

It favors documented REST, streaming, socket, FIX, and official SDK access

Availability, products, and pricing vary by entity and jurisdiction

Free API access does not mean free market data, trading, or exchange fees

Sandbox fills do not establish live execution quality

### Unified execution engines

| Engine | Built-in adapters | Value | Cost |
| --- | --- | --- | --- |
| [NautilusTrader](https://nautilustrader.io/docs/latest/integrations/) | Multiple brokers and crypto venues | Research-to-live parity | Adopts a larger engine |
| [LEAN](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages) | Broad brokerage catalog | Mature live framework | C# core and full-platform overlap |
| [CCXT](https://github.com/ccxt/ccxt) | Many crypto venues | Fast normalized access | Lowest-common-denominator semantics |
| [ib_async](https://github.com/ib-api-reloaded/ib_async) | IBKR | Pythonic async wrapper | Third-party dependency |
| [alpaca-py](https://github.com/alpacahq/alpaca-py) | Alpaca | Official Python SDK | Alpaca-only |

Do not adopt a full execution engine only to save one adapter

Do adopt one when its event, risk, reconciliation, and simulation model all become requirements

### Broker adapter contract

The current `Broker` callable is enough for the tutorial

Live trading requires explicit commands and events

#### Commands

- Connect and authenticate
- Read account and trading status
- Read balances and positions
- Preview an order where supported
- Submit an idempotent order intent
- Amend or cancel an order
- Cancel all scoped orders
- Close or reduce a scoped position

#### Events

- Order accepted
- Order rejected
- Order working
- Partial fill
- Fill
- Cancel accepted
- Cancel rejected
- Position changed
- Balance changed
- Session degraded
- Reconciliation mismatch

#### Stable identifiers

Persist all of these identifiers

- Internal intent id
- Strategy and decision id
- Client order id
- Broker order id
- Parent and leg ids
- Venue execution id
- Account and subaccount id
- Instrument id and provider symbol

Never infer fill identity from timestamp, symbol, and quantity

### Required semantics

| Concern | Rule |
| --- | --- |
| Quantity | Use decimal units and venue increments |
| Price | Use decimal ticks and explicit currency |
| Side | Separate side from signed quantity at the API edge |
| Position effect | Preserve open, close, reduce-only, and short semantics |
| Time in force | Map explicitly and reject unsupported values |
| Sessions | Model regular, extended, overnight, and 24-hour markets |
| Options | Preserve multiplier, expiry, strike, right, and leg relation |
| Idempotency | Reuse one client id for one economic intent |
| Recovery | Query before retrying an ambiguous submission |
| Clock | Check server skew and timestamp windows |
| Rate limit | Budget reads, writes, and reconnect bursts separately |

An ambiguous timeout after submission is not a failed order

Reconcile before retrying it

### Paper evaluation

Paper trading proves authentication, mapping, state transitions, and recovery

It does not prove queue position, market impact, borrow, or live rejection behavior

Run these fault tests before live access

1. Disconnect after sending but before receiving acknowledgement
2. Duplicate an order event
3. Deliver fills before the accepted event
4. Deliver a partial fill followed by cancel
5. Expire the authentication token
6. Hit every documented rate limit
7. Restart with working orders
8. Change a symbol or contract definition
9. Reject an order for tick or lot size
10. Lose a private stream and reconcile from REST

### Adoption sequence

1. Finalize the order and event vocabulary
2. Implement an in-memory deterministic fake broker
3. Add Alpaca paper or the chosen local broker
4. Persist every command and broker event
5. Reconcile account state on every restart
6. Run disconnect and duplicate-event tests
7. Shadow decisions without sending orders
8. Paper trade with realistic local fills and costs
9. Use a separate live account with strict limits
10. Add a second broker only after the contract survives the first
