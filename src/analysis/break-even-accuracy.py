from argparse import ArgumentParser
from pathlib import Path
from sys import stdout
from typing import Any, cast

import numpy as np
import pandas as pd
from arch.bootstrap import StationaryBootstrap
from numpy.typing import NDArray
from pandas import DataFrame


type FloatArray = NDArray[np.float64]

SCHEMA = {"usd_absolute_price_move": "float64", "usd_transaction_cost": "float64"}
SESSION_AXIS = 0
METRIC_AXIS = 1
PRICE_MOVE_METRIC = 0
TRANSACTION_COST_METRIC = 1
BLOCK_SIZE = 5
CONFIDENCE = 0.95
REPLICATIONS = 10_000
SEED = 20_260_816


def _estimate_accuracy(
    usd_absolute_price_moves: FloatArray,
    usd_transaction_costs: FloatArray,
) -> FloatArray:
    assert usd_absolute_price_moves.ndim == usd_transaction_costs.ndim == 1
    assert usd_absolute_price_moves.shape == usd_transaction_costs.shape
    usd_absolute_price_move = float(usd_absolute_price_moves.sum(dtype=np.float64))
    usd_transaction_cost = float(usd_transaction_costs.sum(dtype=np.float64))
    if usd_absolute_price_move <= 0 or usd_transaction_cost > usd_absolute_price_move:
        raise ValueError("break-even accuracy is infeasible")
    return np.array(
        [0.5 + usd_transaction_cost / (2 * usd_absolute_price_move)],
        dtype=np.float64,
    )


def _read_sessions(path: Path) -> FloatArray:
    columns = list(SCHEMA)
    frame = cast(DataFrame, cast(Any, pd).read_csv(path, usecols=columns, dtype=SCHEMA))
    metrics = [
        np.asarray(cast(Any, frame[column]).to_numpy(dtype=np.float64), dtype=np.float64)
        for column in columns
    ]
    sessions = np.ascontiguousarray(np.column_stack(metrics), dtype=np.float64)
    session_count = sessions.shape[SESSION_AXIS]
    assert sessions.shape == (session_count, 2)
    if session_count == 0:
        raise ValueError("the input must contain at least one session")
    if not np.isfinite(sessions).all():
        raise ValueError("the input contains non-finite session values")
    if (sessions < 0.0).any():
        raise ValueError("the input contains negative session values")
    usd_absolute_price_moves = sessions[:, PRICE_MOVE_METRIC]
    usd_transaction_costs = sessions[:, TRANSACTION_COST_METRIC]
    if (usd_transaction_costs > usd_absolute_price_moves).any():
        raise ValueError("transaction cost exceeds absolute price movement")
    if usd_absolute_price_moves.sum(dtype=np.float64) <= 0.0:
        raise ValueError("aggregate absolute price movement must be positive")
    return sessions


def _main() -> None:
    parser = ArgumentParser()
    parser.add_argument("input", type=Path)
    sessions = _read_sessions(parser.parse_args().input)
    usd_absolute_price_moves = sessions[:, PRICE_MOVE_METRIC]
    usd_transaction_costs = sessions[:, TRANSACTION_COST_METRIC]
    estimate = _estimate_accuracy(usd_absolute_price_moves, usd_transaction_costs)[0]
    samples = StationaryBootstrap(
        BLOCK_SIZE,
        usd_absolute_price_moves,
        usd_transaction_costs,
        seed=SEED,
    ).apply(_estimate_accuracy, reps=REPLICATIONS)
    upper_bound = float(np.quantile(samples[:, 0], CONFIDENCE, method="linear"))
    output = pd.DataFrame(
        {
            "estimate": [estimate],
            "confidence_bound_upper": [upper_bound],
            "confidence_probability": [CONFIDENCE],
            "n_session": [sessions.shape[SESSION_AXIS]],
            "n_bootstrap_block": [BLOCK_SIZE],
            "n_bootstrap_replication": [REPLICATIONS],
            "bootstrap_seed": [SEED],
        },
    )
    cast(Any, output).to_csv(stdout, index=False)


if __name__ == "__main__":
    _main()
