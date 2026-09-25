import pandas as pd
import pytest

from market_relationship_discovery.statistics.regime import Regime, RegimeDetector


def test_regime_detector_has_causal_warmup_and_labels() -> None:
    prices = pd.Series([100.0, 101.0, 100.5, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0])

    result = RegimeDetector().detect(prices, window=3, low_quantile=0.2, high_quantile=0.8)

    assert result.labels.iloc[:3].isna().all()
    assert result.labels.iloc[3:].isin([regime.value for regime in Regime]).all()
    assert result.summary()["observations"] == 7


def test_future_mutation_does_not_change_earlier_regimes() -> None:
    prices = pd.Series([100.0, 101.0, 100.5, 102.0, 101.0, 103.0, 102.0, 104.0])
    first = RegimeDetector().detect(prices, window=3)
    changed = prices.copy()
    changed.iloc[-1] = 1000.0
    second = RegimeDetector().detect(changed, window=3)

    pd.testing.assert_series_equal(first.labels.iloc[:-1], second.labels.iloc[:-1])
    pd.testing.assert_series_equal(
        first.rolling_volatility.iloc[:-1], second.rolling_volatility.iloc[:-1]
    )


def test_constant_prices_are_normal_regime() -> None:
    result = RegimeDetector().detect(pd.Series([100.0] * 8), window=3)

    assert result.labels.iloc[3:].eq(Regime.NORMAL_VOLATILITY.value).all()


def test_regime_detector_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError, match="window"):
        RegimeDetector().detect(pd.Series([1.0, 2.0]), window=1)
    with pytest.raises(ValueError, match="quantiles"):
        RegimeDetector().detect(pd.Series([1.0, 2.0]), low_quantile=0.8, high_quantile=0.2)
