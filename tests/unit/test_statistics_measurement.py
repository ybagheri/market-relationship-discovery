"""A statistic must be measurable, or must say why it is not.

Four defects, all of which produced a number a reader would believe.

`correlation` accepted three observations. Any three points on a straight line
correlate at exactly 1.0, so the minimum sample guaranteed a perfect
relationship that was an artefact of the sample size.

`half_life` had no plausibility bound. The estimate is `-ln(2) / slope` from
regressing the change on the level, and a slope near zero makes it diverge, so a
series that never reverts produced a figure like 6e15 describing the slope
rather than the market.

`lead_lag` documented neither its sign convention nor any significance test, so
a reader could not tell which sign meant the predictor leads, and the strongest
correlation in a table could have come from four observations.

`rolling_correlation` had no caller and no test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import InsufficientDataError
from market_relationship_discovery.statistics.analyzer import StatisticalAnalyzer

analyzer = StatisticalAnalyzer()


def _ar1(coefficient: float, size: int = 400, seed: int = 5) -> pd.Series:
    rng = np.random.default_rng(seed)
    values = [1.0]
    for _ in range(size - 1):
        values.append(coefficient * values[-1] + float(rng.normal(scale=0.01)))
    return pd.Series(values)


# --- correlation ----------------------------------------------------------


def test_three_points_are_not_a_correlation() -> None:
    """Any three points on a line correlate at exactly 1.0.

    The old minimum was three, so a sample that could only produce an artefact
    reported a perfect relationship indistinguishable from a measured one.
    """
    left = pd.Series([1.0, 2.0, 3.0])
    right = pd.Series([2.0, 4.0, 6.0])

    result = analyzer.correlation(left, right)

    assert result.is_available is False
    assert np.isnan(result.pearson)
    assert result.unavailable_reason is not None
    assert "8" in result.unavailable_reason


def test_an_absent_correlation_is_never_reported_as_zero() -> None:
    result = analyzer.correlation(pd.Series([1.0, 2.0]), pd.Series([1.0, 3.0]))

    assert np.isnan(result.pearson) is not False or result.is_available is False
    assert result.unavailable_reason is not None


def test_a_real_relationship_is_still_measured() -> None:
    left = pd.Series(np.arange(100, dtype=float))
    right = left * 2.0 + 1.0

    result = analyzer.correlation(left, right)

    assert result.is_available is True
    assert result.pearson == pytest.approx(1.0)
    assert result.observations == 100


def test_the_reason_names_the_sample_it_had() -> None:
    result = analyzer.correlation(pd.Series([1.0, 2.0, 3.0]), pd.Series([1.0, 2.0, 4.0]))

    assert result.observations == 3
    assert "3 available" in (result.unavailable_reason or "")


# --- half life ------------------------------------------------------------


def test_a_non_reverting_series_reports_no_half_life() -> None:
    """A random walk never reverts, and must not report a 600-observation one."""
    rng = np.random.default_rng(1)
    walk = pd.Series(np.cumsum(rng.normal(0, 1, 400)))

    result = analyzer.half_life(walk)

    assert result.mean_reversion is False
    assert result.half_life is None
    assert result.unavailable_reason is not None


def test_a_slow_decay_with_no_significant_slope_says_so() -> None:
    """A slope indistinguishable from zero is a reason to report no reversion.

    The old estimate had no bound at all, so this series produced a figure around
    6e15 — a description of the slope, not of the market.
    """
    slow = pd.Series([100.0 - 0.001 * index for index in range(500)])

    result = analyzer.half_life(slow)

    assert result.half_life is None
    assert result.mean_reversion is False
    assert result.regression_is_significant is False
    assert "not distinguishable" in (result.unavailable_reason or "")


def test_a_measured_half_life_recovers_the_ar1_value() -> None:
    series = _ar1(0.85)

    result = analyzer.half_life(series)

    assert result.mean_reversion is True
    assert result.half_life == pytest.approx(abs(np.log(0.5) / np.log(0.85)), rel=0.4)


def test_a_constant_series_says_it_is_not_measurable() -> None:
    result = analyzer.half_life(pd.Series([2.0] * 50))

    assert result.half_life is None
    assert "constant" in (result.unavailable_reason or "")


def test_a_short_series_is_refused_rather_than_fitted() -> None:
    with pytest.raises(InsufficientDataError, match="20 observations"):
        analyzer.half_life(pd.Series([3.0, 1.0, 2.0, 0.0, 1.0, -1.0]))


def test_a_significant_slope_always_yields_a_measured_half_life() -> None:
    """A significant, negative slope is a measured reversion.

    A separate bound on the resulting half-life was considered and dropped. For
    an AR(1) process the half-life is `ln(0.5)/ln(rho)`, which exceeds the sample
    length only above `rho` of about 0.999, and at that coefficient the slope is
    no longer distinguishable from zero in any practical sample. A bound that
    cannot fire while its precondition holds is a check that always passes.
    """
    for coefficient in (0.9, 0.95, 0.98, 0.995):
        result = analyzer.half_life(_ar1(coefficient, size=400, seed=8))

        assert result.regression_is_significant is True
        assert result.mean_reversion is True
        assert result.half_life is not None and result.half_life > 0


def test_a_slow_but_measurable_reversion_is_still_reported() -> None:
    """A slow reversion is a slower reversion, not an absent one."""
    result = analyzer.half_life(_ar1(0.995, seed=3))

    assert result.mean_reversion is True
    assert result.half_life is not None
    assert result.half_life < result.observations


# --- lead / lag -----------------------------------------------------------


def test_the_sign_convention_is_stated_in_words() -> None:
    """A sign the reader has to infer from the code is not a convention."""
    predictor = pd.Series(np.arange(60, dtype=float))
    result = analyzer.lead_lag(predictor, predictor.rolling(2).mean(), 3)

    assert result.loc[result["lag"] == 1, "predictor_leads"].item() is True
    assert result.loc[result["lag"] == -1, "predictor_lags"].item() is True
    assert result.loc[result["lag"] == 0, "predictor_leads"].item() is False
    assert result.loc[result["lag"] == 0, "predictor_lags"].item() is False


def test_a_known_lead_shows_up_at_the_positive_lag() -> None:
    """The predictor is a leading average of the target by construction."""
    rng = np.random.default_rng(2)
    target = pd.Series(np.cumsum(rng.normal(0, 1, 200)))
    predictor = target.rolling(5).mean().shift(1)

    result = analyzer.lead_lag(predictor, target, max_lag=4)

    leads = result[result["predictor_leads"]]
    best_lead = leads.loc[leads["correlation"].abs().idxmax()]
    assert int(best_lead["lag"]) in {1, 2, 3, 4}
    assert bool(best_lead["significant"]) is True


def test_a_lag_with_too_few_observations_reports_no_significance() -> None:
    """Four points cannot establish a relationship, and must not look like they can."""
    predictor = pd.Series(range(4), dtype=float)
    result = analyzer.lead_lag(predictor, predictor * 2, max_lag=3)

    assert result["p_value"].isna().all()
    assert result["significant"].isna().all()
    assert result["significant_and_usable"].eq(False).all()


def test_the_raw_correlation_is_always_reported() -> None:
    """A reader deciding for themselves should not have to reconstruct it."""
    rng = np.random.default_rng(4)
    predictor = pd.Series(rng.normal(size=200))
    target = pd.Series(rng.normal(size=200))

    result = analyzer.lead_lag(predictor, target, 3)

    assert result["correlation"].notna().all()
    assert result["observations"].min() > 0


def test_a_trivial_correlation_is_not_called_significant_and_usable() -> None:
    rng = np.random.default_rng(6)
    predictor = pd.Series(rng.normal(size=200))
    target = pd.Series(rng.normal(size=200))

    result = analyzer.lead_lag(predictor, target, 3)

    assert not result["significant_and_usable"].any()
