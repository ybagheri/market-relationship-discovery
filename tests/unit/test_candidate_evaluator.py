import numpy as np
import pandas as pd

from market_relationship_discovery.discovery.engine import CandidateStatus, DiscoveryCandidate
from market_relationship_discovery.discovery.evaluator import (
    EvaluatedCandidate,
    GraphCandidateEvaluator,
)
from market_relationship_discovery.discovery.ranker import (
    CandidateRankingConfig,
    RidgeCandidateRanker,
)


def _prices() -> pd.DataFrame:
    index = pd.date_range("2026-09-25", periods=60, freq="h", tz="UTC")
    first = np.linspace(1.0, 1.3, 60)
    second = np.linspace(1.0, 1.1, 60)
    return pd.DataFrame({"A": first, "B": second, "C": first * second}, index=index)


def test_evaluator_scores_exact_relationship() -> None:
    candidate = DiscoveryCandidate("A_B", "C", "A * B", CandidateStatus.RESEARCH_CANDIDATE)

    result = GraphCandidateEvaluator().evaluate(
        _prices(), [candidate], minimum_observations=30, regime_window=5
    )[0]

    assert result.candidate.status is CandidateStatus.REQUIRES_FURTHER_VALIDATION
    assert result.summary["mean_absolute_discrepancy"] == 0.0
    assert "rolling_beta" in result.frame
    assert result.summary["beta_stability"]["valid_windows"] > 0
    assert result.summary["cointegration_stationarity"]["status"] == "available"
    assert result.frame["next_abs_zscore"].iloc[-1] != result.frame["next_abs_zscore"].iloc[-1]


def test_evaluator_marks_missing_columns_as_requires_data() -> None:
    candidate = DiscoveryCandidate("A_B", "C", "A * B", CandidateStatus.RESEARCH_CANDIDATE)

    result = GraphCandidateEvaluator().evaluate(
        _prices()[["A"]], [candidate], minimum_observations=3
    )[0]

    assert result.candidate.status is CandidateStatus.REQUIRES_DATA
    assert result.summary["missing_symbols"] == ["B", "C"]


def _evaluation(name: str, multiplier: float) -> EvaluatedCandidate:
    index = pd.date_range("2026-09-25", periods=40, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "zscore": np.linspace(0.1, 1.0, 40) * multiplier,
            "discrepancy_volatility": np.linspace(0.01, 0.1, 40) * multiplier,
            "regime": ["normal_volatility"] * 40,
            "next_abs_zscore": np.linspace(0.2, 1.2, 40) * multiplier,
        }
    )
    candidate = DiscoveryCandidate(name, name, "A", CandidateStatus.REQUIRES_FURTHER_VALIDATION)
    return EvaluatedCandidate(
        candidate,
        frame,
        {"pearson": 1.0, "spearman": 1.0, "half_life": 2.0},
    )


def test_ridge_ranker_is_deterministic_and_orders_stronger_candidate_first() -> None:
    result = RidgeCandidateRanker().rank(
        [_evaluation("weak", 0.2), _evaluation("strong", 2.0)],
        CandidateRankingConfig(minimum_train_rows=10),
    )

    assert [candidate.name for candidate in result.candidates] == ["strong", "weak"]
    assert [candidate.rank for candidate in result.candidates] == [1, 2]
    assert result.model == "numpy_ridge"
    assert result.training_end < result.evaluation_start
    assert (
        result.candidates[0].predicted_mean_next_abs_zscore
        > result.candidates[1].predicted_mean_next_abs_zscore
    )
