---
name: spec
---

# strategies

- each strategy occupies one module in `src/bot/strategies`
- each module starts with its complete strategy specification
- imports follow the module docstring
- each module exports one class named `Strategy`
- `Strategy` subclasses `lumibot.strategies.Strategy`
- the same class supports backtests and trading
- the runner supplies shared settings through Lumibot `parameters`
- the strategy uses native Lumibot data, order, and lifecycle methods

```python:surface
"""
Name: {name}
Purpose: {purpose}
Instrument: {instrument}
Market: {calendar-and-time-zone}
Schedule: {frequency-and-window}
Data: {bars-and-completion-rule}
Entry: {signal-and-order}
Sizing: {risk-and-quantity-rule}
Risk: {trade-day-and-position-limits}
Exit: {protective-and-time-exits}
State: {session-and-restart-state}
Failure: {fail-closed-rules}
Backtest: {fees-slippage-and-lookahead-rules}
"""

from typing import ClassVar

from lumibot.strategies import Strategy as LumibotStrategy


class Strategy(LumibotStrategy):
    parameters: ClassVar[dict[str, object]] = {}

    def initialize(self) -> None:
        ...

    def on_trading_iteration(self) -> None:
        ...
```

# opening-range

- the first proposed module is `src/bot/strategies/opening_range.py`
- the opening range uses the first five completed regular-session minute bars
- the first close outside that range consumes the session opportunity
- the entry uses a native Lumibot OTO order with one protective stop child
- the strategy contains no custom broker, order, or persistence framework

```python:surface
"""
Name: opening-range
Purpose: Trade the first confirmed breakout from SPY's initial five-minute range.
Instrument: SPY with whole-share orders.
Market: NYSE in America/New_York time.
Schedule: Run each minute. Accept entries after 09:35 and before 15:55.
Data: Use completed regular-session minute bars. Ignore the current bar and after-hours bars.
Entry: Buy after the first close above the range. Sell short after the first close below it.
Sizing: Risk starting portfolio value times risk_per_trade_max. Cap whole shares by buying power.
Risk: Permit one entry and one position. When session loss reaches starting portfolio value times risk_per_day_max, stop entries.
Exit: Use the opposite range boundary as the stop. Close any position at 15:55.
State: Track the session date and consumed opportunity. Reconcile positions and tagged orders at startup.
Failure: If data or broker state is unknown, do not enter. If OTO submission fails, consume the opportunity.
Backtest: Use completed bars only. Apply the fee and slippage settings to each fill.
"""

from decimal import Decimal
from typing import ClassVar

from lumibot.entities import Order
from lumibot.strategies import Strategy as LumibotStrategy


class Strategy(LumibotStrategy):
    parameters: ClassVar[dict[str, object]] = {
        "instrument": "SPY",
        "risk_per_day_max": 0.02,
        "risk_per_trade_max": 0.005,
    }

    def initialize(self) -> None:
        self.sleeptime = "1M"
        self.minutes_before_closing = 5
        self.set_market("NYSE")
        ...

    def on_trading_iteration(self) -> None:
        ...

    def before_market_closes(self) -> None:
        ...

    def _submit_entry(
        self,
        side: Order.OrderSide,
        quantity: int,
        stop_price: Decimal,
    ) -> None:
        order = self.create_order(
            str(self.parameters["instrument"]),
            quantity,
            side,
            order_class=Order.OrderClass.OTO,
            secondary_stop_price=float(stop_price),
            time_in_force="day",
        )
        self.submit_order(order)
```

```python:private
opening_range() -> tuple[Decimal, Decimal] | None
    return the high and low from the first five completed session bars

first_breakout(high: Decimal, low: Decimal) -> tuple[Order.OrderSide, Decimal] | None
    return only the first completed close outside the range

position_quantity(entry: Decimal, stop: Decimal) -> int
    divide the trade risk by price risk
    cap the result by buying power
    round down to whole shares

session_is_blocked() -> bool
    block after one opportunity or the maximum session loss

close_session() -> None
    cancel strategy orders
    close the strategy position
```
