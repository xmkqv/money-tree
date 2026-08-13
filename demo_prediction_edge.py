from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from enum import IntEnum
from statistics import mean, stdev

SHARES = Decimal("1")
SPREAD = Decimal("0.03")
COMMISSION_RATE = Decimal("0")
SEC_RATE = Decimal("0.0000206")
TAF_RATE = Decimal("0.000195")
CAT_RATE = Decimal("0.000003")
CENT = Decimal("0.01")


class Direction(IntEnum):
    SHORT = -1
    LONG = 1


@dataclass(frozen=True, slots=True)
class Mark:
    decision_at: datetime
    decision_price: Decimal
    fill_at: datetime
    fill_reference: Decimal


@dataclass(frozen=True, slots=True)
class Trade:
    entry: Mark
    exit: Mark
    direction: Direction
    entry_price: Decimal
    exit_price: Decimal

    @property
    def decision_pnl(self) -> Decimal:
        return SHARES * self.direction * (self.exit.decision_price - self.entry.decision_price)

    @property
    def fill_pnl(self) -> Decimal:
        return SHARES * self.direction * (self.exit_price - self.entry_price)

    @property
    def execution_cost(self) -> Decimal:
        return self.decision_pnl - self.fill_pnl

    @property
    def sell_value(self) -> Decimal:
        price = self.exit_price if self.direction is Direction.LONG else self.entry_price
        return SHARES * price


@dataclass(frozen=True, slots=True)
class Fees:
    commission: Decimal
    sec: Decimal
    taf: Decimal
    cat: Decimal

    @property
    def total(self) -> Decimal:
        return self.commission + self.sec + self.taf + self.cat


def mark(time: str, decision_price: str, fill_reference: str) -> Mark:
    decision_at = datetime.fromisoformat(f"2026-08-13T{time}:00-04:00")
    return Mark(
        decision_at,
        Decimal(decision_price),
        decision_at + timedelta(minutes=1),
        Decimal(fill_reference),
    )


MARKS = (
    mark("09:30", "302.53", "303.01"),
    mark("09:45", "303.46", "303.09"),
    mark("10:00", "304.52", "304.488"),
    mark("10:15", "305.85", "305.06"),
    mark("10:30", "305.83", "305.35"),
    mark("10:45", "304.865", "304.85"),
    mark("11:00", "304.9", "304.99"),
    mark("11:15", "304.15", "304.09"),
    mark("11:30", "303.67", "303.6199"),
    mark("11:45", "303.42", "303.52"),
    mark("12:00", "302.8109", "302.745"),
    mark("12:15", "303.36", "303.372"),
    mark("12:30", "303.305", "303.17"),
    mark("12:45", "303.21", "303.35"),
    mark("13:00", "303.1199", "303.01"),
    mark("13:15", "303.04", "303.0188"),
    mark("13:30", "303.335", "303.325"),
    mark("13:45", "303.645", "303.76"),
    mark("14:00", "303.45", "303.29"),
    mark("14:15", "303.315", "303.335"),
    mark("14:30", "303.4", "303.37"),
    mark("14:45", "303.4887", "303.585"),
    mark("15:00", "303.064", "303.21"),
)


def find_direction(change: Decimal) -> Direction:
    if change == 0:
        raise ValueError("direction requires a nonzero change")
    return Direction.LONG if change > 0 else Direction.SHORT


def make_trade(entry: Mark, exit: Mark, direction: Direction) -> Trade:
    half_spread = SPREAD / 2
    entry_price = entry.fill_reference + direction * half_spread
    exit_price = exit.fill_reference - direction * half_spread
    return Trade(entry, exit, direction, entry_price, exit_price)


def make_strategy_trades() -> list[Trade]:
    return [
        make_trade(
            MARKS[index],
            MARKS[index + 1],
            find_direction(MARKS[index].decision_price - MARKS[index - 1].decision_price),
        )
        for index in range(1, len(MARKS) - 1)
    ]


def make_oracle_trades() -> list[Trade]:
    return [
        make_trade(
            MARKS[index],
            MARKS[index + 1],
            find_direction(MARKS[index + 1].decision_price - MARKS[index].decision_price),
        )
        for index in range(1, len(MARKS) - 1)
    ]


def round_fee(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


def fees(trades: list[Trade]) -> Fees:
    sell_value = sum((trade.sell_value for trade in trades), Decimal())
    executed_shares = 2 * SHARES * len(trades)
    return Fees(
        round_fee(COMMISSION_RATE * sell_value),
        round_fee(SEC_RATE * sell_value),
        round_fee(TAF_RATE * SHARES * len(trades)),
        round_fee(CAT_RATE * executed_shares),
    )


def required_accuracy(trades: list[Trade], cost: Decimal) -> Decimal:
    correct = [trade.decision_pnl for trade in trades if trade.decision_pnl > 0]
    wrong = [-trade.decision_pnl for trade in trades if trade.decision_pnl < 0]
    win = mean(correct)
    loss = mean(wrong)
    return (loss + cost) / (win + loss)


def lower_bound(trades: list[Trade], fee: Decimal) -> Decimal:
    fee_per_trade = fee / len(trades)
    returns = [trade.fill_pnl - fee_per_trade for trade in trades]
    block_size = 4
    complete = len(returns) - len(returns) % block_size
    block_means = [
        mean(returns[index : index + block_size]) for index in range(0, complete, block_size)
    ]
    return (
        mean(block_means) - Decimal("1.645") * stdev(block_means) / Decimal(len(block_means)).sqrt()
    )


def money(value: Decimal) -> str:
    return f"{value:+.4f}"


def print_trade(trade: Trade) -> None:
    side = "L" if trade.direction is Direction.LONG else "S"
    entry_decision = trade.entry.decision_at.strftime("%H:%M")
    entry_fill = trade.entry.fill_at.strftime("%H:%M")
    exit_decision = trade.exit.decision_at.strftime("%H:%M")
    exit_fill = trade.exit.fill_at.strftime("%H:%M")
    print(
        f"{entry_decision}@{trade.entry.decision_price:.4f} "
        f"{entry_fill}@{trade.entry_price:.4f} "
        f"{exit_decision}@{trade.exit.decision_price:.4f} "
        f"{exit_fill}@{trade.exit_price:.4f} "
        f"{side} move={money(trade.decision_pnl)} "
        f"slip={money(trade.execution_cost)} fill={money(trade.fill_pnl)}"
    )


def main() -> None:
    trades = make_strategy_trades()
    oracle = make_oracle_trades()
    trade_fees = fees(trades)
    oracle_fees = fees(oracle)
    fill_pnl = sum((trade.fill_pnl for trade in trades), Decimal())
    net_pnl = fill_pnl - trade_fees.total
    oracle_net_pnl = sum((trade.fill_pnl for trade in oracle), Decimal()) - oracle_fees.total
    correct = sum(trade.decision_pnl > 0 for trade in trades)
    accuracy = Decimal(correct) / len(trades)
    fee_per_trade = trade_fees.total / len(trades)
    spread_fee_floor = SPREAD * SHARES + fee_per_trade
    cost_per_trade = mean(trade.execution_cost for trade in trades) + fee_per_trade
    accuracy_required = required_accuracy(trades, cost_per_trade)
    bound = lower_bound(trades, trade_fees.total)
    capital = max(trade.entry_price for trade in trades) * SHARES

    print("AAPL | Nasdaq 2026-08-13 ET | 15m momentum")
    print("execution | 1 share | 1m fill delay | 15:07 spread=$0.03")
    print("Alpaca 2026-07-20 | commission=0 sec=0.0000206 taf=0.000195 cat=0.000003")
    print("entry_decision entry_fill exit_decision exit_fill side decision_move slippage fill_pnl")
    for trade in trades:
        print_trade(trade)
    print(f"trades={len(trades)} correct={correct} accuracy={accuracy:.2%}")
    print(
        f"spread_fee_floor={money(spread_fee_floor)} "
        f"break_even_move={money(cost_per_trade)} required_accuracy={accuracy_required:.2%}"
    )
    print(
        f"commission={money(trade_fees.commission)} sec={money(trade_fees.sec)} "
        f"taf={money(trade_fees.taf)} cat={money(trade_fees.cat)}"
    )
    print(f"fill_pnl={money(fill_pnl)} fees={money(trade_fees.total)} net_pnl={money(net_pnl)}")
    print(f"capital={capital:.4f} return={net_pnl / capital:.4%}")
    print(f"oracle_net_pnl={money(oracle_net_pnl)}")
    print(f"hour_block_95pct_lower={money(bound)} information={bound > 0}")


if __name__ == "__main__":
    main()
