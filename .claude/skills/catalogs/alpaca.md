[alpaca][alpaca]
    commission-free us equities, options, and crypto with a rest + websocket api
    paper trading runs on a separate host with the same api surface
    available to clients in 30+ countries; cash and margin accounts
    broker api is a distinct product from trading api (omnibus/fully-disclosed accounts)
    benzinga news and logos are served through the alpaca api since 2022
    [market data][market-data]
        historical us equity data starts in 2016
        sip combines cta and utp data across reported us exchange volume
        [historical bars][historical-bars]
            historical bars default to raw adjustment and ascending order
            response pages contain at most 10000 points and expose next_page_token
    [sdk][sdk]
        official sdks: python, .net/c#, node/ts, go, java
        openapi specs published for broker, trading, and market data
        community sdks: rust (apca), r, scala, ruby, elixir, java (petersoj)
        [alpaca py][alpaca-py]
            official python sdk, 1.4k stars, active 2026-08
            supersedes alpaca-trade-api-python, which is archived at 1.9k stars since 2024-12
        [apca][apca]
            community rust sdk, 204 stars, active 2026-07
            ships apcacli as a companion command line client
        [alpaca java][alpaca-java]
            community java sdk, 254 stars, active 2026-07
    [frameworks][frameworks]
        official partner list is 17 entries and skews no-code and saas
        no-code: trellis, composer, streak, tradetron, algobulls, breaking equity
        research/backtest: quantrocket, blueshift, wealth-lab, arcade trader, algorum
        adjacent: tradingview, slack, zapier, alexa, passiv, predictnow.ai
        [lumibot][lumibot]
            open-source python framework, 1.9k stars, active 2026-08
            alpaca is a first-class broker alongside ibkr, tradier, schwab, tradovate, ccxt
            covers backtest and live from one strategy class; lowest-friction python path to alpaca
        [lean][lean]
            official quantconnect brokerage plugin in c#, 17 stars, active 2026-08
            covers equities, options, and crypto; works in lean cli and local platform
            cloud deploys run on quantconnect colocated servers against your alpaca balance
        [nautilus][nautilus]
            no alpaca adapter exists; 18 shipped adapters as of 2026-08 and alpaca is not one
            [rfc 3374][nautilus-rfc] opened 2026-01-01, still open, no assignee, no milestone, no linked pr
            proposal targets the native httpclient/websocket layer with no alpaca-py dependency
            writing one means a livedataclient + liveexecutionclient pair off the bybit or ibkr template
        [freqtrade alpaca][freqtrade-alpaca]
            fork adding alpaca to freqtrade, 0 stars, stale since 2025-01
            treat as abandoned

## refs

[alpaca]: https://alpaca.markets
[market-data]: https://docs.alpaca.markets/us/docs/about-market-data-api
[historical-bars]: https://docs.alpaca.markets/us/reference/stockbars
[sdk]: https://docs.alpaca.markets/us/docs/sdks-and-tools
[alpaca-py]: https://github.com/alpacahq/alpaca-py
[apca]: https://github.com/d-e-s-o/apca
[alpaca-java]: https://github.com/Petersoj/alpaca-java
[frameworks]: https://alpaca.markets/integrations
[lumibot]: https://github.com/Lumiwealth/lumibot
[lean]: https://github.com/QuantConnect/Lean.Brokerages.Alpaca
[nautilus]: https://github.com/nautechsystems/nautilus_trader
[nautilus-rfc]: https://github.com/nautechsystems/nautilus_trader/issues/3374
[freqtrade-alpaca]: https://github.com/aidinstinct/freqtrade-alpaca
