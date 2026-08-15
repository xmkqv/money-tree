# Code map

```text
money-tree/
├── pyproject.toml
│   ├ mt = money_tree.cli:main (surface,foe)
│   └ money-tree-worker = money_tree.worker:main (surface)
├── .env.example
│   ├ MONEY_TREE_STRATEGY: StrategyName (surface)
│   ├ MONEY_TREE_MODE: TradingMode (surface)
│   ├ ALPACA_API_KEY: str (surface)
│   ├ ALPACA_API_SECRET: str (surface)
│   ├ ALPACA_LIVE_API_KEY: str (surface)
│   └ ALPACA_LIVE_API_SECRET: str (surface)
├── railway.toml
│   └ uv run --no-sync money-tree-worker (surface)
├── src/
│   └── money_tree/
│       ├── __init__.py
│       │   ├ Direction (surface)
│       │   ├ MomentumLongStrategy (surface)
│       │   ├ OpeningRangeStrategy (surface)
│       │   ├ OrderRole (surface)
│       │   ├ OrderSide (surface)
│       │   ├ StrategyName (surface)
│       │   ├ Tfb50Strategy (surface,foe)
│       │   └ TradingMode (surface)
│       ├── model.py
│       │   ├ StrategyName = OPENING_RANGE | MOMENTUM_LONG | TFB_50
│       │   ├ TradingMode = PAPER | LIVE
│       │   ├ Direction = LONG | FLAT | SHORT
│       │   ├ OrderSide = BUY | SELL
│       │   ├ OrderRole = ENTRY | PROTECTIVE_STOP | FLATTEN
│       │   ├ PositionState(quantity, average_entry_price, realized_profit_and_loss)
│       │   ├ PositionState.direction -> Direction
│       │   ├ PositionState.record_fill(OrderSide, Decimal, Decimal) -> None
│       │   ├ PositionState.calculate_profit_and_loss(Decimal) -> Decimal
│       │   ├ PositionState.set_flat() -> None
│       │   ├ OwnedOrderState(identifiers)
│       │   ├ OwnedOrderState.ids -> set[str]
│       │   ├ OwnedOrderState.get_id(OrderRole) -> str | None
│       │   ├ OwnedOrderState.set_id(OrderRole, str | None) -> None
│       │   ├ OpeningRangeState(protective_stop_price)
│       │   ├ MomentumLongState(entry_price, initial_protective_stop_price, active_protective_stop_price, trail_activation_price, highest_price)
│       │   ├ Tfb50State(entered_on, initial_protective_stop_price, active_protective_stop_price)
│       │   ├ StrategyState = OpeningRangeState | MomentumLongState | Tfb50State
│       │   ├ create_strategy_state(StrategyName) -> StrategyState
│       │   ├ TradingState(strategy, instrument, session_date, entered, disabled, position, orders, strategy_state)
│       │   ├ TradingState.validate() -> None
│       │   ├ TradingState.start_session(date, keep_position: bool) -> None
│       │   └ TradingState.clear_strategy_position() -> None
│       ├── bars.py
│       │   ├ normalize_price_bars(pl.DataFrame) -> pl.DataFrame
│       │   └ market_datetime_expression(pl.DataFrame, str) -> pl.Expr
│       ├── indicators.py
│       │   ├ wilder_average(pl.Expr, int) -> pl.Expr
│       │   ├ indicator_plan(pl.DataFrame) -> pl.LazyFrame
│       │   └ calculate_indicators(pl.DataFrame) -> pl.DataFrame
│       ├── opening_range.py
│       │   ├ OpeningRange(high_price, low_price)
│       │   ├ Breakout(closed_at, close_price, direction, protective_stop_price)
│       │   ├ to_market_datetime(object) -> datetime
│       │   ├ find_breakout(pl.DataFrame, date, datetime) -> Breakout | None
│       │   └ should_flatten(datetime) -> bool
│       ├── risk.py
│       │   ├ size_position(Decimal, Decimal, Direction, Decimal) -> Decimal
│       │   └ has_reached_loss_limit(PositionState, Decimal, Decimal) -> bool
│       ├── broker.py
│       │   ├ BrokerConfig(api_key, api_secret, mode)
│       │   ├ BrokerConfig.to_lumibot() -> dict[str, str | bool]
│       │   ├ InstrumentRequirements(fractional, short)
│       │   ├ AccountSnapshot(position_quantity, position_average_entry_price, open_order_ids)
│       │   ├ load_broker_config(TradingMode) -> BrokerConfig
│       │   ├ connect_broker(BrokerConfig) -> TradingClient
│       │   ├ verify_account(TradingClient) -> None
│       │   ├ verify_instrument(TradingClient, str, InstrumentRequirements) -> None
│       │   ├ get_account_snapshot(TradingClient, str) -> AccountSnapshot
│       │   └ reconcile_account(AccountSnapshot, TradingState) -> None
│       ├── state.py
│       │   ├ LoadTradingStateError(ValueError)
│       │   ├ StateStore(Path | None, strategy: StrategyName, instrument: str)
│       │   ├ StateStore.load() -> TradingState
│       │   └ StateStore.save(TradingState) -> None
│       ├── cli.py
│       │   ├ StrategyConfig(strategy_class, bar_interval, requirements)
│       │   ├ default_state_path(StrategyName, TradingMode) -> Path
│       │   ├ build_parser() -> argparse.ArgumentParser (surface,foe)
│       │   │   ├ mt backtest --instrument str --strategy StrategyName (surface,foe)
│       │   │   ├ mt trade --instrument str --strategy StrategyName (surface,foe)
│       │   │   └ mt trade --instrument str --strategy StrategyName --LIVE (surface,foe)
│       │   ├ run_backtest(StrategyName, str, date, date, Path) -> dict[str, Any]
│       │   ├ run_trade(StrategyName, str, TradingMode, Path, confirmation: str | None) -> None
│       │   └ main() -> None (surface,foe)
│       ├── worker.py
│       │   ├ WorkerConfig(strategy, mode)
│       │   ├ load_worker_config(Mapping[str, str] | None) -> WorkerConfig
│       │   ├ run_worker(WorkerConfig) -> None
│       │   └ main() -> None (surface)
│       └── strategies/
│           ├── __init__.py
│           │   ├ MomentumLongStrategy (surface)
│           │   ├ OpeningRangeStrategy (surface)
│           │   └ Tfb50Strategy (surface,foe)
│           ├── base.py
│           │   ├ TradingStrategy(Strategy)
│           │   ├ TradingStrategy.on_partially_filled_order(Position, Order, float, float, float) -> None
│           │   ├ TradingStrategy.on_filled_order(Position, Order, float, float, float) -> None
│           │   ├ TradingStrategy.on_canceled_order(Order) -> None
│           │   ├ TradingStrategy.on_error_order(Order, Exception | None) -> None
│           │   └ TradingStrategy.on_abrupt_closing() -> None
│           ├── opening_range.py
│           │   ├ OpeningRangeStrategy(TradingStrategy) (surface)
│           │   ├ OpeningRangeStrategy.opening_range_state -> OpeningRangeState
│           │   ├ OpeningRangeStrategy.initialize() -> None
│           │   ├ OpeningRangeStrategy.on_trading_iteration() -> None
│           │   └ OpeningRangeStrategy.before_market_closes() -> None
│           ├── momentum_long.py
│           │   ├ EntryDecision(protective_stop_price)
│           │   ├ decide_entry(pl.DataFrame, swing_span: int, price_tick: float) -> EntryDecision | None
│           │   ├ should_flatten(pl.DataFrame) -> bool
│           │   ├ calculate_trailing_stop_price(float, float, float, multiplier: float, price_tick: float) -> float
│           │   ├ MomentumLongStrategy(TradingStrategy) (surface)
│           │   ├ MomentumLongStrategy.momentum_state -> MomentumLongState
│           │   ├ MomentumLongStrategy.initialize() -> None
│           │   └ MomentumLongStrategy.on_trading_iteration() -> None
│           └── tfb_50.py
│               ├ EntryDecision(protective_stop_price)
│               ├ ExitSignal = PREVIOUS_LOW | EMERGENCY
│               ├ latest_confirmed_swing_low(pl.DataFrame, swing_span: int, price_tick: float) -> float | None
│               ├ highest_confirmed_swing_low_since(pl.DataFrame, date, swing_span: int, price_tick: float) -> float | None
│               ├ decide_entry(pl.DataFrame, sma_slope_span: int, swing_span: int, price_tick: float) -> EntryDecision | None
│               ├ decide_exit(pl.DataFrame) -> ExitSignal | None
│               ├ Tfb50Strategy(TradingStrategy) (surface)
│               ├ Tfb50Strategy.tfb_state -> Tfb50State
│               ├ Tfb50Strategy.initialize() -> None
│               └ Tfb50Strategy.on_trading_iteration() -> None
├── exps/
│   ├── world.py
│   │   ├ FloatArray = NDArray[np.float64]
│   │   ├ IntArray = NDArray[np.int64]
│   │   ├ SessionRange(started_on, ended_before)
│   │   ├ AlpacaCredentials(api_key, api_secret)
│   │   ├ BarClose(closed_at, price)
│   │   ├ MarketObservations(instrument, session_range, session_dates, decision_prices, execution_prices, n_excluded_session)
│   │   ├ OrderBatch(directions)
│   │   ├ ExplicitCosts(commission_by_session, section_31_by_session, finra_taf_by_session, cat_by_session)
│   │   ├ RoundTripResult(n_round_trip_by_session, share_quantity_by_session, absolute_price_moves, execution_costs, explicit_costs)
│   │   ├ ResearchStudy(observations, momentum)
│   │   ├ parse_session_range(str) -> SessionRange
│   │   ├ load_alpaca_credentials() -> AlpacaCredentials
│   │   ├ observe_bar_closes(str, SessionRange, AlpacaCredentials) -> list[BarClose]
│   │   ├ observe_session_dates(SessionRange, AlpacaCredentials) -> tuple[date, ...]
│   │   ├ iter_decision_times(date) -> Iterator[datetime]
│   │   ├ observe_market(str, SessionRange, Iterable[BarClose], Iterable[date]) -> MarketObservations
│   │   ├ round_fee_by_session(FloatArray) -> FloatArray
│   │   ├ calculate_explicit_costs(FloatArray, FloatArray, FloatArray) -> ExplicitCosts
│   │   ├ execute_orders(MarketObservations, OrderBatch) -> RoundTripResult
│   │   ├ decide_momentum_orders(MarketObservations) -> OrderBatch
│   │   ├ build_research_study(str, SessionRange, AlpacaCredentials, tuple[date, ...]) -> ResearchStudy
│   │   └ build_research_studies(SessionRange) -> tuple[ResearchStudy, ...]
│   ├── break_even_accuracy.py
│   │   ├ AccuracyEvidence(estimate, confidence_bound_upper, bootstrap_block_size)
│   │   ├ build_session_frame(ResearchStudy) -> pl.DataFrame
│   │   ├ validate_session_frame(pl.DataFrame) -> None
│   │   ├ build_balanced_panel(pl.DataFrame) -> pl.DataFrame
│   │   ├ calculate_accuracy(float, float) -> float
│   │   ├ calculate_break_even_accuracy(FloatArray, FloatArray) -> float
│   │   ├ calculate_accuracy_evidence(FloatArray, FloatArray, replication_count: int, seed: int) -> AccuracyEvidence
│   │   ├ calculate_accuracy_evidence_by_window(dict[str, tuple[FloatArray, FloatArray]], replication_count: int, seed: int, worker_count: int | None) -> dict[str, AccuracyEvidence]
│   │   ├ summarize_sessions(pl.LazyFrame, *groups: str) -> pl.LazyFrame
│   │   ├ summarize_rolling_accuracy(pl.LazyFrame) -> pl.LazyFrame
│   │   ├ build_stock_results(pl.DataFrame) -> pl.DataFrame
│   │   ├ build_panel_results(pl.DataFrame, bootstrap_replication_count: int, bootstrap_seed: int, worker_count: int | None) -> pl.DataFrame
│   │   ├ concat_results(list[pl.DataFrame]) -> pl.DataFrame
│   │   └ main() -> pl.DataFrame (surface)
│   └── backtests/
│       ├── test_opening_range.py
│       │   └ FindBreakoutTest
│       ├── test_momentum_long.py
│       │   ├ MomentumIndicatorsTest
│       │   └ MomentumRulesTest
│       └── test_tfb_50.py (foe)
│           ├ Tfb50EntryTest
│           ├ Tfb50ExitTest
│           └ Tfb50ProtectiveStopTest
└── data/
    └── cache/ (generated)
```

# Useful library constructs

| lib | method | use |
| --- | --- | --- |
| `alpaca-py 0.44.0` | `TradingClient(..., paper=bool)` | The client selects a paper account or a live account. |
| `alpaca-py 0.44.0` | `get_account()` | The client reads account status and trading restrictions. |
| `alpaca-py 0.44.0` | `get_asset(symbol)` | The client reads trading, fractional trading, short selling, and borrowing capabilities. |
| `alpaca-py 0.44.0` | `get_all_positions()` | The client supplies broker positions for reconciliation. |
| `alpaca-py 0.44.0` | `get_orders(GetOrdersRequest)` | The client supplies open orders for one instrument. |
| `alpaca-py 0.44.0` | `get_calendar(GetCalendarRequest)` | The client supplies expected market session dates. |
| `alpaca-py 0.44.0` | `StockHistoricalDataClient.get_stock_bars(StockBarsRequest)` | The client supplies adjusted or raw historical bars from a selected feed. |
| `lumibot 4.5.26` | `Strategy.run_backtest(...)` | The framework runs a strategy against an Alpaca historical data source. |
| `lumibot 4.5.26` | `Strategy.run_live()` | The framework starts the live iteration and order event loop. |
| `lumibot 4.5.26` | `get_historical_prices(...)` | A strategy reads recent bars at its configured interval. |
| `lumibot 4.5.26` | `get_last_price()` and `get_position()` | A strategy reads the current mark and broker position. |
| `lumibot 4.5.26` | `create_order()`, `submit_order()`, and `cancel_order()` | A strategy controls entry, protection, and flatten orders. |
| `lumibot 4.5.26` | `on_filled_order()` and order event callbacks | A strategy records fills, cancellations, and broker errors. |
| `lumibot 4.5.26` | `get_tracked_order()` and `wait_orders_clear()` | The broker restores owned orders and waits until order cancellation is complete. |
| `polars 1.43.2` | `DataFrame.lazy()` and `LazyFrame.collect()` | The plan defers indicator, signal, and research calculations until collection. |
| `polars 1.43.2` | `select()`, `with_columns()`, and `filter()` | Expressions define bar normalization and trading signals without row loops. |
| `polars 1.43.2` | `rolling_mean()`, `rolling_sum()`, `ewm_mean()`, and `over()` | Window expressions calculate indicators and rolling evidence. |
| `polars 1.43.2` | `Schema`, strict constructors, and `cast(..., strict=True)` | Explicit schemas reject invalid research data types. |
| `polars 1.43.2` | `group_by()`, `join()`, and `concat()` | Lazy plans create stock summaries, balanced panels, and aligned results. |
| `numpy 2.5.1` | `ndarray` broadcasting and boolean indexing | Arrays execute all simulated round trips without Python row loops. |
| `numpy 2.5.1` | `where()`, `sign()`, and `add.reduceat()` | Vector operations decide orders and aggregate observations by session. |
| `numpy 2.5.1` | `nextafter()` and `ceil()` | The calculation rounds regulatory fees to cents without a downward float error. |
| `arch 8.0.0` | `optimal_block_length()` | The estimator selects a stationary block size from the influence series. |
| `arch 8.0.0` | `StationaryBootstrap(...)` | The bootstrap keeps local dependence across market sessions. |
| `arch 8.0.0` | `conf_int(..., method="studentized", tail="upper")` | The bootstrap calculates a one-sided upper confidence bound. |
