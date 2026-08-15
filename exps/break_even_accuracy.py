from dataclasses import dataclass
from itertools import pairwise
from math import ceil, isfinite

import numpy as np
from arch.bootstrap import StationaryBootstrap, optimal_block_length

from exps.world import (
    DECISION_INTERVAL,
    EXECUTION_DELAY,
    INSTRUMENT,
    N_SESSION_MIN,
    USD_SPREAD,
    FloatArray,
    IntArray,
    ResearchStudy,
    build_research_study,
    parse_session_range,
)

N_BOOTSTRAP_REPLICATION = 10_000
SEED_BOOTSTRAP = 20_260_815
PROBABILITY_CONFIDENCE = 0.95


@dataclass(frozen=True, slots=True)
class BreakEvenAccuracySample:
    absolute_price_move_by_session: FloatArray
    transaction_cost_by_session: FloatArray
    n_directional_observation: int


@dataclass(frozen=True, slots=True)
class BreakEvenAccuracyEvidence:
    stationary_block_size: int
    break_even_accuracy: float
    upper_break_even_accuracy: float


def sum_by_session(values: FloatArray, counts: IntArray) -> FloatArray:
    if values.size != int(counts.sum()):
        raise ValueError("session counts must match the value count")
    boundaries = np.concatenate(([0], counts.cumsum()))
    return np.array(
        [values[start:end].sum() for start, end in pairwise(boundaries)],
        dtype=np.float64,
    )


def build_break_even_accuracy_sample(study: ResearchStudy) -> BreakEvenAccuracySample:
    result = study.momentum[DECISION_INTERVAL]
    absolute_price_move_by_session = sum_by_session(
        result.absolute_price_moves,
        result.n_round_trip_by_session,
    )
    execution_cost_by_session = sum_by_session(
        result.execution_costs,
        result.n_round_trip_by_session,
    )
    return BreakEvenAccuracySample(
        absolute_price_move_by_session,
        execution_cost_by_session + result.explicit_costs.by_session,
        int(np.count_nonzero(result.absolute_price_moves)),
    )


def calculate_break_even_accuracy(
    absolute_price_move_by_session: FloatArray,
    transaction_cost_by_session: FloatArray,
) -> FloatArray:
    absolute_price_move = float(absolute_price_move_by_session.sum())
    if absolute_price_move <= 0:
        raise RuntimeError("break-even accuracy requires positive price moves")
    transaction_cost = float(transaction_cost_by_session.sum())
    if transaction_cost < 0:
        raise RuntimeError("break-even accuracy requires a nonnegative transaction cost")
    accuracy = 0.5 + transaction_cost / (2 * absolute_price_move)
    return np.array([accuracy], dtype=np.float64)


def calculate_break_even_accuracy_evidence(
    sample: BreakEvenAccuracySample,
) -> BreakEvenAccuracyEvidence:
    absolute_price_moves = sample.absolute_price_move_by_session
    transaction_costs = sample.transaction_cost_by_session
    if absolute_price_moves.size != transaction_costs.size:
        raise ValueError("accuracy inputs must contain the same sessions")
    if absolute_price_moves.size < N_SESSION_MIN:
        raise RuntimeError(f"inference requires at least {N_SESSION_MIN} complete sessions")
    if not np.isfinite(absolute_price_moves).all() or not np.isfinite(transaction_costs).all():
        raise RuntimeError("accuracy inputs must be finite")
    if (absolute_price_moves < 0).any():
        raise RuntimeError("absolute price moves must be nonnegative")

    break_even_accuracy = float(
        calculate_break_even_accuracy(absolute_price_moves, transaction_costs)[0]
    )
    cost_ratio = float(transaction_costs.sum() / absolute_price_moves.sum())
    influence_by_session = transaction_costs - cost_ratio * absolute_price_moves
    block_lengths = optimal_block_length(influence_by_session)
    stationary_block_length = float(block_lengths["stationary"].iloc[0])
    if not isfinite(stationary_block_length) or stationary_block_length <= 0:
        raise RuntimeError("arch could not estimate a stationary block length")
    stationary_block_size = ceil(stationary_block_length)

    bootstrap = StationaryBootstrap(
        stationary_block_size,
        absolute_price_moves,
        transaction_costs,
        seed=SEED_BOOTSTRAP,
    )
    confidence_interval = bootstrap.conf_int(
        calculate_break_even_accuracy,
        reps=N_BOOTSTRAP_REPLICATION,
        method="bca",
        size=PROBABILITY_CONFIDENCE,
        tail="upper",
    )
    upper_break_even_accuracy = float(confidence_interval[1, 0])
    if not isfinite(break_even_accuracy) or not isfinite(upper_break_even_accuracy):
        raise RuntimeError("arch returned non-finite accuracy evidence")
    return BreakEvenAccuracyEvidence(
        stationary_block_size,
        break_even_accuracy,
        upper_break_even_accuracy,
    )


def print_claim(
    study: ResearchStudy,
    sample: BreakEvenAccuracySample,
    evidence: BreakEvenAccuracyEvidence,
) -> None:
    observations = study.observations
    print(
        f"{INSTRUMENT} sip feed | {observations.session_range.started_on} "
        f"<= session < {observations.session_range.ended_before}"
    )
    print("intent | upper bound on directional accuracy required to break even")
    print("boundary | isolated research | not product-strategy evidence")
    print("strategy | momentum[15m] | 1 share | flat after each horizon")
    print("assumption | correct and incorrect forecasts have equal mean absolute price moves")
    print(
        f"execution | delay={int(EXECUTION_DELAY.total_seconds() // 60)}m "
        f"assumed_spread=${USD_SPREAD:.2f} no_market_impact=true"
    )
    print(
        f"sample | complete_sessions={len(observations.session_dates)} "
        f"excluded_sessions={observations.n_excluded_session} "
        f"directional_observations={sample.n_directional_observation}"
    )
    print(
        f"stationary_bootstrap | block_size={evidence.stationary_block_size} "
        f"replications={N_BOOTSTRAP_REPLICATION} seed={SEED_BOOTSTRAP}"
    )
    print(
        f"break_even_accuracy | estimate={evidence.break_even_accuracy:.2%} "
        f"one_sided_95pct_upper={evidence.upper_break_even_accuracy:.2%}"
    )


def main() -> None:
    study = build_research_study(parse_session_range("break-even-accuracy"))
    sample = build_break_even_accuracy_sample(study)
    evidence = calculate_break_even_accuracy_evidence(sample)
    print_claim(study, sample, evidence)


if __name__ == "__main__":
    main()
