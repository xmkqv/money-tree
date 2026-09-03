from datetime import datetime
from pathlib import Path

from .types import StrategyName


def run(
    strategy_name: StrategyName,
    symbols: list[str],
    start: datetime,
    end: datetime,
) -> Path:
    from .backtest import run as run_backtest

    output_dir = Path("runs") / f"{strategy_name}-{start:%Y%m%d}-{end:%Y%m%d}"
    run_backtest(strategy_name, start, end, symbols=symbols, output_dir=output_dir)
    print(output_dir)
    return output_dir
