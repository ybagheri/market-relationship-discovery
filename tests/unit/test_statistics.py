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
