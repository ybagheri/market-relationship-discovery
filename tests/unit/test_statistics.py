import numpy as np
import pandas as pd
import pytest

from market_relationship_discovery.statistics.analyzer import StatisticalAnalyzer


def test_rolling_zscore_uses_only_rolling_window() -> None:
    spread = pd.Series(range(1, 12), dtype=float)
    result = StatisticalAnalyzer.rolling_zscore(spread, 5)

    assert pd.isna(result.iloc[:4]).all()
    assert result.iloc[4] == pytest.approx(1.4142135623730951)


def test_half_life_detects_reverting_process() -> None:
    spread = pd.Series([3.0, 1.0, 2.0, 0.0, 1.0, -1.0, 0.5, -0.5])
    result = StatisticalAnalyzer().half_life(spread)

    assert result.mean_reversion is True
    assert result.half_life is not None and result.half_life > 0


def test_lead_lag_reports_requested_range() -> None:
    predictor = pd.Series(range(20), dtype=float)
    target = predictor.shift(1)
    result = StatisticalAnalyzer.lead_lag(predictor, target, 2)

    assert result["lag"].tolist() == [-2, -1, 0, 1, 2]


def test_rolling_beta_recovers_known_slope() -> None:
    benchmark = pd.Series(np.arange(1.0, 31.0))
    benchmark_returns = benchmark.pct_change(fill_method=None)
    target_values = [100.0]
    for value in benchmark_returns.iloc[1:]:
        target_values.append(target_values[-1] * (1.0 + 3.0 * value))
    target = pd.Series(target_values)

    result = StatisticalAnalyzer().rolling_beta(target, benchmark, 5)

    assert result.values.iloc[:5].isna().all()
    assert result.values.dropna().iloc[-1] == pytest.approx(3.0)
    assert result.summary["valid_windows"] == 25
    assert result.summary["sign_consistency"] == 1.0


def test_rolling_beta_is_causal() -> None:
    benchmark = pd.Series(np.arange(1.0, 31.0))
    target = 5.0 + 3.0 * benchmark
    first = StatisticalAnalyzer().rolling_beta(target, benchmark, 5)
    changed = target.copy()
    changed.iloc[-1] = 1000.0
    second = StatisticalAnalyzer().rolling_beta(changed, benchmark, 5)

    pd.testing.assert_series_equal(first.values.iloc[:-1], second.values.iloc[:-1])


def test_cointegration_stationarity_reports_residual_diagnostics() -> None:
    generator = np.random.default_rng(20260926)
    benchmark = np.cumsum(generator.normal(size=400)) + 100.0
    target = 2.0 * benchmark + generator.normal(scale=0.05, size=400)

    result = StatisticalAnalyzer.cointegration_stationarity(pd.Series(target), pd.Series(benchmark))

    assert result["status"] == "available"
    assert result["unavailable_reason"] is None
    assert result["engle_granger_method"] == "ols_residual_augmented_dickey_fuller"
    assert result["adf_method"] == "statsmodels_adfuller_autolag_aic"
    assert result["kpss_method"] == "statsmodels_kpss_level_autolag"
    assert result["cointegrated_at_significance"] is True
    assert result["stationarity_tests_agree"] is True


def test_cointegrated_random_walk_pair_is_not_reported_as_cointegrated() -> None:
    """A strongly correlated but non-cointegrated pair must not be labelled so.

    Regression on an ill-conditioned near unit-root pair previously produced an
    augmented Dickey-Fuller statistic of order 1e16 with a zero p-value, which
    reported a confident cointegrated result for a relationship that a proper
    test rejects. The statistic must stay in a plausible range and the pair must
    not be labelled cointegrated.
    """
    generator = np.random.default_rng(20260926)
    benchmark = pd.Series(np.cumsum(generator.normal(size=400)) + 100.0)
    target = pd.Series(np.cumsum(generator.normal(size=400)) + 50.0)

    result = StatisticalAnalyzer.cointegration_stationarity(target, benchmark)

    assert result["status"] == "available"
    assert abs(float(result["engle_granger_statistic"])) < 100.0
    assert 0.0 <= float(result["engle_granger_p_value"]) <= 1.0
    assert result["cointegrated_at_significance"] is False
    assert result["stationarity_tests_agree"] is True


def test_stationarity_diagnostics_report_a_reason_when_unavailable() -> None:
    result = StatisticalAnalyzer.cointegration_stationarity(
        pd.Series(np.arange(1.0, 21.0)),
        pd.Series(np.arange(1.0, 21.0)),
    )

    assert result["status"] == "unavailable"
    assert "30 aligned observations" in str(result["unavailable_reason"])


def test_cointegration_stationarity_handles_degenerate_input() -> None:
    result = StatisticalAnalyzer.cointegration_stationarity(
        pd.Series([1.0] * 40),
        pd.Series(np.arange(1.0, 41.0)),
    )

    assert result["status"] == "unavailable"
    assert result["adf_p_value"] is None
    assert "constant" in str(result["unavailable_reason"])


def test_statistical_parameters_are_validated() -> None:
    with pytest.raises(ValueError, match="window"):
        StatisticalAnalyzer().rolling_beta(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), 1)
    with pytest.raises(ValueError, match="significance"):
        StatisticalAnalyzer.cointegration_stationarity(
            pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), 1.0
        )
