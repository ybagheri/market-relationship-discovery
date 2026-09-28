import numpy as np
import pandas as pd
import pytest

from market_relationship_discovery.discovery.engine import CandidateStatus, DiscoveryCandidate
from market_relationship_discovery.discovery.evaluator import (
    EvaluatedCandidate,
    GraphCandidateEvaluator,
)
from market_relationship_discovery.discovery.ranker import (
    CandidateRankingConfig,
    RidgeCandidateRanker,
    _expanding_pearson,
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
    assert result.summary["cointegration_stationarity"]["status"] == "unavailable"
    assert "constant" in str(result.summary["cointegration_stationarity"]["unavailable_reason"])
    assert result.frame["next_abs_zscore"].iloc[-1] != result.frame["next_abs_zscore"].iloc[-1]


def test_evaluator_reports_a_collinear_pair_as_unavailable_not_cointegrated() -> None:
    """A benchmark identical to the target cannot support a cointegration test.

    The synthetic value here is ``A * B`` and the observed series is that same
    product plus noise an order of magnitude below the price, so the benchmark
    explains the target almost exactly. ``statsmodels.coint`` reports that
    condition with a statistic of ``-inf`` and a p-value of zero, which it
    documents as numerically unstable rather than as a test outcome. Reporting
    a zero p-value would certify a cointegrated relationship the test never
    measured, so the result must be an explicit unavailable reason.
    """
    generator = np.random.default_rng(20260926)
    index = pd.date_range("2026-09-25", periods=60, freq="h", tz="UTC")
    first = np.linspace(1.0, 1.3, 60)
    second = np.linspace(1.0, 1.1, 60)
    prices = pd.DataFrame(
        {
            "A": first,
            "B": second,
            "C": first * second + generator.normal(scale=1e-4, size=60),
        },
        index=index,
    )
    candidate = DiscoveryCandidate("A_B", "C", "A * B", CandidateStatus.RESEARCH_CANDIDATE)

    result = GraphCandidateEvaluator().evaluate(
        prices, [candidate], minimum_observations=30, regime_window=5
    )[0]

    stationarity = result.summary["cointegration_stationarity"]
    assert stationarity["status"] == "unavailable"
    assert "collinear" in str(stationarity["unavailable_reason"])
    assert stationarity["adf_p_value"] is None
    assert stationarity["cointegrated_at_significance"] is None


def test_evaluator_reports_stationarity_for_a_cointegrated_relationship() -> None:
    """A benchmark that does not already contain the target must still be tested.

    The observed series holds a stationary spread around a cointegrating
    relationship with the benchmark, which is the case the test is meant to
    cover. A collinearity guard must not suppress a genuine result.
    """
    generator = np.random.default_rng(20260926)
    index = pd.date_range("2026-09-25", periods=200, freq="h", tz="UTC")
    first = np.cumsum(generator.normal(size=200)) + 100.0
    second = np.cumsum(generator.normal(size=200)) + 50.0
    spread = generator.normal(scale=0.2, size=200)
    prices = pd.DataFrame(
        {"X1": first, "X2": second, "OBSERVED": first + second + spread},
        index=index,
    )
    candidate = DiscoveryCandidate(
        "OBSERVED_X1X2", "OBSERVED", "X1 + X2", CandidateStatus.RESEARCH_CANDIDATE
    )

    result = GraphCandidateEvaluator().evaluate(
        prices, [candidate], minimum_observations=30, regime_window=5
    )[0]

    stationarity = result.summary["cointegration_stationarity"]
    assert stationarity["status"] == "available"
    assert stationarity["adf_p_value_is_regressor_adjusted"] is True
    assert abs(float(stationarity["engle_granger_statistic"])) < 100.0


def test_evaluator_marks_missing_columns_as_requires_data() -> None:
    candidate = DiscoveryCandidate("A_B", "C", "A * B", CandidateStatus.RESEARCH_CANDIDATE)

    result = GraphCandidateEvaluator().evaluate(
        _prices()[["A"]], [candidate], minimum_observations=3
    )[0]

    assert result.candidate.status is CandidateStatus.REQUIRES_DATA
    assert result.summary["missing_symbols"] == ["B", "C"]


def _evaluation(name: str, multiplier: float) -> EvaluatedCandidate:
    index = pd.date_range("2026-09-25", periods=40, freq="h", tz="UTC")
    # A drifting second series so the expanding correlation is defined and
    # varies through the sample, the way a real candidate's fit would.
    actual = np.linspace(1.0, 1.3, 40) + np.sin(np.arange(40)) * 0.01
    synthetic = actual * (1.0 - 0.02 * multiplier) + np.cos(np.arange(40)) * 0.005
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "actual": actual,
            "synthetic": synthetic,
            "zscore": np.linspace(0.1, 1.0, 40) * multiplier,
            "discrepancy_volatility": np.linspace(0.01, 0.1, 40) * multiplier,
            "regime": ["normal_volatility"] * 40,
            "next_abs_zscore": np.linspace(0.2, 1.2, 40) * multiplier,
        }
    )
    candidate = DiscoveryCandidate(name, name, "A", CandidateStatus.REQUIRES_FURTHER_VALIDATION)
    return EvaluatedCandidate(candidate, frame, {"pearson": 1.0, "spearman": 1.0, "half_life": 2.0})


def test_one_bad_symbol_does_not_destroy_every_candidate_in_the_run() -> None:
    """A target that crosses zero degrades one candidate, not the whole run.

    A spread target such as ``A - B`` is negative for part of any real sample,
    and the regime detector requires positive prices. Previously that raised out
    of ``evaluate`` and took every other candidate in the run with it.
    """
    prices = _prices()
    prices["SPREAD"] = prices["A"] - prices["B"]
    candidates = [
        DiscoveryCandidate("A_B", "C", "A * B", CandidateStatus.RESEARCH_CANDIDATE),
        DiscoveryCandidate("A_spread", "SPREAD", "A - B", CandidateStatus.RESEARCH_CANDIDATE),
    ]

    results = GraphCandidateEvaluator().evaluate(
        prices, candidates, minimum_observations=30, regime_window=10
    )

    assert [result.candidate.name for result in results] == ["A_B", "A_spread"]
    assert results[0].candidate.status is CandidateStatus.REQUIRES_FURTHER_VALIDATION
    assert results[1].candidate.status is CandidateStatus.REQUIRES_DATA
    assert results[1].summary["unavailable_reason"]


def test_a_zero_denominator_drops_only_the_affected_observation() -> None:
    """One zero print invalidates one bar, not the entire candidate."""
    prices = _prices()
    prices["ZERO"] = np.linspace(1.0, 1.3, len(prices))
    prices.loc[prices.index[5], "ZERO"] = 0.0
    candidate = DiscoveryCandidate(
        "A_div_ZERO", "C", "A / ZERO", CandidateStatus.RESEARCH_CANDIDATE
    )

    result = GraphCandidateEvaluator().evaluate(
        prices, [candidate], minimum_observations=30, regime_window=10
    )[0]

    assert result.candidate.status is CandidateStatus.REQUIRES_FURTHER_VALIDATION
    assert len(result.frame) == len(prices) - 1
    assert np.isfinite(result.frame["synthetic"].to_numpy()).all()


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


def test_ranking_features_are_computed_from_past_observations_only() -> None:
    """Rewriting the future must not change any feature row.

    A feature summarised over a candidate's whole series encodes the evaluation
    period, so the model would be scored out of sample against the answer. Every
    row is compared here against a frame whose later half has been replaced.
    """
    original = _evaluation("candidate", 1.0)
    frame = original.frame.copy()
    changed_at = len(frame) // 2
    before = original.frame["timestamp"].iloc[changed_at]
    frame.loc[changed_at:, "actual"] = frame.loc[changed_at:, "actual"] * 5.0
    frame.loc[changed_at:, "synthetic"] = frame.loc[changed_at:, "synthetic"] * -3.0
    future_changed = EvaluatedCandidate(original.candidate, frame, original.summary)

    original_prefix = [row for row in RidgeCandidateRanker._rows([original]) if row[0] < before]
    changed_prefix = [
        row for row in RidgeCandidateRanker._rows([future_changed]) if row[0] < before
    ]

    assert changed_prefix == original_prefix
    assert original_prefix, "the prefix must contain rows for the comparison to mean anything"


def test_ranking_features_carry_no_whole_sample_summary_statistics() -> None:
    """Full-sample correlations and half-life must not be model inputs."""
    assert not {
        "pearson",
        "spearman",
        "half_life",
        "observation_fraction",
    } & set(RidgeCandidateRanker.feature_names)
    assert "expanding_pearson" in RidgeCandidateRanker.feature_names


def test_expanding_pearson_is_undefined_during_warmup() -> None:
    """Rows with too little history are dropped, not filled with a perfect score."""
    index = pd.date_range("2026-09-25", periods=30, freq="h", tz="UTC")
    left = pd.Series(np.linspace(1.0, 1.3, 30), index=index)
    right = pd.Series(np.linspace(1.0, 1.4, 30) + np.sin(np.arange(30)) * 0.02, index=index)

    values = _expanding_pearson(left, right, minimum_observations=10)

    assert all(np.isnan(value) for value in values[:9])
    assert all(0.0 < value <= 1.0 for value in values[9:])


def test_expanding_pearson_matches_pandas_on_price_level_data() -> None:
    """A one-pass closed form must agree with a direct computation.

    Correlating price-level series means recovering a small covariance from much
    larger accumulated products, so the formula has to be centred or it loses
    precision. The bound is inclusive because rounding must not push the result
    outside the statistic's own range.
    """
    index = pd.date_range("2026-09-25", periods=40, freq="h", tz="UTC")
    generator = np.random.default_rng(20260926)
    left = pd.Series(1.0 + np.cumsum(generator.normal(scale=1e-4, size=40)), index=index)
    right = pd.Series(1.3 + np.cumsum(generator.normal(scale=1e-4, size=40)), index=index)

    values = _expanding_pearson(left, right, minimum_observations=5)

    for position in range(4, len(left)):
        assert values[position] == pytest.approx(
            left.iloc[: position + 1].corr(right.iloc[: position + 1]),
            abs=1e-9,
        )
    assert max(abs(value) for value in values if not np.isnan(value)) <= 1.0


def test_expanding_pearson_is_undefined_for_a_constant_window() -> None:
    index = pd.date_range("2026-09-25", periods=30, freq="h", tz="UTC")
    left = pd.Series(np.ones(30), index=index)
    right = pd.Series(np.linspace(1.0, 1.4, 30), index=index)

    values = _expanding_pearson(left, right, minimum_observations=5)

    assert all(np.isnan(value) for value in values)
