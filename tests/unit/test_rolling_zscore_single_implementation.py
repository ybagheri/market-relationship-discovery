"""One transform, not two copies that happen to agree today.

`CausalFeatureBuilder.rolling_zscore` was a second implementation of
`StatisticalAnalyzer.rolling_zscore`. They agreed on every input tried, but this
one feeds the ranking model while the other is what the report describes, so a
change applied to one would silently leave the other measuring something else.

A comment saying they are the same is not a guarantee, so the agreement is
asserted on the inputs that distinguish them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_relationship_discovery.backtesting.multi_stage import CausalFeatureBuilder
from market_relationship_discovery.statistics.analyzer import StatisticalAnalyzer

rng = np.random.default_rng(3)

CASES: dict[str, pd.Series] = {
    "random walk": pd.Series(rng.normal(0, 1, 200)),
    "with missing values": pd.Series([1.0, 2.0, np.nan, 4.0, 5.0] * 30),
    "constant then variable": pd.Series([1.0] * 40 + list(rng.normal(0, 1, 60))),
    "entirely constant": pd.Series([2.0] * 100),
    "constant variance": pd.Series(rng.normal(-5, 0.001, 80)),
    "short series": pd.Series(rng.normal(0, 1, 50)),
}


@pytest.mark.parametrize("name", sorted(CASES))
@pytest.mark.parametrize("window", [2, 5, 20])
def test_both_names_compute_the_same_transform(name: str, window: int) -> None:
    series = CASES[name]

    reported = StatisticalAnalyzer.rolling_zscore(series, window)
    model_input = CausalFeatureBuilder.rolling_zscore(series, window)

    np.testing.assert_allclose(reported.to_numpy(), model_input.to_numpy(), equal_nan=True)
    assert reported.index.equals(model_input.index)


@pytest.mark.parametrize("window", [1, 0, -3])
def test_both_names_refuse_the_same_invalid_windows(window: int) -> None:
    series = pd.Series([1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="window must be at least two"):
        StatisticalAnalyzer.rolling_zscore(series, window)
    with pytest.raises(ValueError, match="window must be at least two"):
        CausalFeatureBuilder.rolling_zscore(series, window)


def test_a_constant_window_is_undefined_rather_than_infinite() -> None:
    """A zero standard deviation cannot be divided by, and must not become inf.

    An infinite z-score in a model input is a value no estimator can use, so it
    has to be absent rather than present and unusable.
    """
    result = CausalFeatureBuilder.rolling_zscore(pd.Series([2.0] * 40), 5)

    assert result.isna().all()


def test_the_model_input_reads_no_future_observation() -> None:
    """Changing the last value must not change any earlier z-score.

    This is what makes the feature usable as a ranking-model input, and it is
    the property the two copies could each lose independently.
    """
    base = pd.Series(rng.normal(0, 1, 120))
    changed = base.copy()
    changed.iloc[-1] = 1e6

    original = CausalFeatureBuilder.rolling_zscore(base, 10)
    modified = CausalFeatureBuilder.rolling_zscore(changed, 10)

    np.testing.assert_allclose(original.to_numpy()[:-1], modified.to_numpy()[:-1], equal_nan=True)
    assert not np.isclose(original.iloc[-1], modified.iloc[-1])
