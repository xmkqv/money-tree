from dataclasses import dataclass
from math import ceil, isfinite

import numpy as np
from arch.bootstrap import SPA, StationaryBootstrap, optimal_block_length
from world import (
    INSTRUMENT,
    N_SESSION_MIN,
    FloatArray,
    ResearchStudy,
    build_research_study,
    format_money,
    parse_session_range,
)

N_BOOTSTRAP_REPLICATION = 10_000
SEED_BOOTSTRAP = 20_260_813
PROBABILITY_CONFIDENCE = 0.95
PROBABILITY_SIGNIFICANCE = 0.05


@dataclass(frozen=True, slots=True)
class PredictiveEdgeEvidence:
    stationary_block_size: int
    mean_net_profit_and_loss: float
    lower_mean_net_profit_and_loss: float
    spa_consistent_p_value: float
    supported: bool


def calculate_mean(values: FloatArray) -> FloatArray:
    return np.array([values.mean()], dtype=np.float64)


def calculate_predictive_edge_evidence(
    net_profit_and_loss_by_session: FloatArray,
) -> PredictiveEdgeEvidence:
    if net_profit_and_loss_by_session.size < N_SESSION_MIN:
        raise RuntimeError(f"inference requires at least {N_SESSION_MIN} complete sessions")
    block_lengths = optimal_block_length(net_profit_and_loss_by_session)
    stationary_block_length = float(block_lengths["stationary"].iloc[0])
    if not isfinite(stationary_block_length) or stationary_block_length <= 0:
        raise RuntimeError("arch could not estimate a stationary block length")
    stationary_block_size = ceil(stationary_block_length)
    bootstrap = StationaryBootstrap(
        stationary_block_size,
        net_profit_and_loss_by_session,
        seed=SEED_BOOTSTRAP,
    )
    confidence_interval = bootstrap.conf_int(
        calculate_mean,
        reps=N_BOOTSTRAP_REPLICATION,
        method="bca",
        size=PROBABILITY_CONFIDENCE,
        tail="lower",
    )
    lower_mean_net_profit_and_loss = float(confidence_interval[0, 0])
    spa = SPA(
        np.zeros_like(net_profit_and_loss_by_session),
        -net_profit_and_loss_by_session[:, None],
        block_size=stationary_block_size,
        reps=N_BOOTSTRAP_REPLICATION,
        bootstrap="stationary",
        studentize=True,
        nested=False,
        seed=SEED_BOOTSTRAP,
    )
    spa.compute()
    spa_consistent_p_value = float(spa.pvalues["consistent"])
    if not isfinite(lower_mean_net_profit_and_loss) or not isfinite(spa_consistent_p_value):
        raise RuntimeError("arch returned non-finite evidence")
    supported = (
        lower_mean_net_profit_and_loss > 0 and spa_consistent_p_value < PROBABILITY_SIGNIFICANCE
    )
    return PredictiveEdgeEvidence(
        stationary_block_size,
        float(net_profit_and_loss_by_session.mean()),
        lower_mean_net_profit_and_loss,
        spa_consistent_p_value,
        supported,
    )


def print_claim(study: ResearchStudy, evidence: PredictiveEdgeEvidence) -> None:
    result = "supported" if evidence.supported else "not_supported"
    observations = study.observations
    print(
        f"{INSTRUMENT} sip feed | {observations.session_range.started_on} "
        f"<= session < {observations.session_range.ended_before}"
    )
    print("boundary | isolated research | not product-strategy evidence")
    print("estimand | mean session net profit and loss of 15-minute momentum")
    print("benchmark | cash | session loss=0")
    print(
        f"sample | complete_sessions={len(observations.session_dates)} "
        f"excluded_sessions={observations.n_excluded_session}"
    )
    print(
        f"stationary_bootstrap | block_size={evidence.stationary_block_size} "
        f"replications={N_BOOTSTRAP_REPLICATION} seed={SEED_BOOTSTRAP}"
    )
    print(
        f"bca | mean_net_profit_and_loss={format_money(evidence.mean_net_profit_and_loss)} "
        "one_sided_95pct_lower="
        f"{format_money(evidence.lower_mean_net_profit_and_loss)}"
    )
    print(f"spa | consistent_p_value={evidence.spa_consistent_p_value:.4f}")
    print(f"predictive_edge | evidence={result}")


def main() -> None:
    study = build_research_study(parse_session_range("predictive-edge"))
    evidence = calculate_predictive_edge_evidence(
        study.fifteen_minute_momentum.net_profit_and_loss_by_session
    )
    print_claim(study, evidence)


if __name__ == "__main__":
    main()
