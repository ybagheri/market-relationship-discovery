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
    benchmark = pd.Series(np.arange(1.0, 41.0))
    target = 2.0 + 0.5 * benchmark

    result = StatisticalAnalyzer.cointegration_stationarity(target, benchmark)

    assert result["status"] == "available"
    assert result["engle_granger_method"] == "ols_residual_adf_approximation"
    assert result["adf_method"] == "fixed_lag1_ols_normal_approximation"
    assert result["kpss_method"] == "level_cusum_chi_square_approximation"
    assert result["cointegrated_at_significance"] is True
    assert result["stationarity_tests_agree"] is True


def test_cointegration_stationarity_handles_degenerate_input() -> None:
    result = StatisticalAnalyzer.cointegration_stationarity(
        pd.Series([1.0] * 20),
        pd.Series(np.arange(1.0, 21.0)),
    )

    assert result["status"] == "unavailable"
    assert result["adf_p_value"] is None


def test_statistical_parameters_are_validated() -> None:
    with pytest.raises(ValueError, match="window"):
        StatisticalAnalyzer().rolling_beta(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), 1)
    with pytest.raises(ValueError, match="significance"):
        StatisticalAnalyzer.cointegration_stationarity(
            pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), 1.0
        )
