import math
import warnings
from dataclasses import dataclass
from math import log

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tools.sm_exceptions import (
    CollinearityWarning,
    InterpolationWarning,
    MissingDataError,
)
from statsmodels.tsa.stattools import adfuller, coint, kpss

from market_relationship_discovery.domain.errors import InsufficientDataError

#: Smallest sample for a correlation to mean anything.
#:
#: Three points on any straight line correlate at exactly 1.0, so a three
#: observation correlation reports a perfect relationship that is an artefact of
#: having three points and not a measurement. Two points are always perfectly
#: correlated or undefined.
MINIMUM_CORRELATION_OBSERVATIONS = 8

#: Smallest sample for a half-life regression to be worth fitting.
MINIMUM_HALF_LIFE_OBSERVATIONS = 20

#: Smallest sample for a lagged correlation to be distinguishable from noise.
MINIMUM_LEAD_LAG_OBSERVATIONS = 8

#: |correlation| below which a lagged relationship is treated as absent.
MINIMUM_LEAD_LAG_ABSOLUTE_CORRELATION = 0.2


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    pearson: float
    spearman: float
    observations: int
    #: Why the correlation is absent, when it is. A reported value of 0.0 would
    #: be indistinguishable from a measured absence of relationship.
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.unavailable_reason is None


@dataclass(frozen=True, slots=True)
class HalfLifeResult:
    half_life: float | None
    mean_reversion: bool
    observations: int
    #: Why the estimate is absent or unbounded, when it is.
    unavailable_reason: str | None = None
    #: Whether the regression's slope is distinguishable from zero at all. A
    #: slope that is not is a reason to report no reversion, not a very long
    #: one.
    regression_is_significant: bool | None = None


@dataclass(frozen=True, slots=True)
class RollingBetaResult:
    values: pd.Series
    summary: dict[str, object]


class StatisticalAnalyzer:
    def correlation(self, left: pd.Series, right: pd.Series) -> CorrelationResult:
        """Correlate two series, or report why the sample cannot support one.

        Three observations are refused. Any three points on a straight line
        correlate at exactly 1.0, so the old three-observation minimum returned
        a perfect relationship that was an artefact of the sample size rather
        than a measurement, and a caller had no way to tell it from a real one.
        """
        aligned = pd.concat([left, right], axis=1).dropna()
        count = len(aligned)
        if count < MINIMUM_CORRELATION_OBSERVATIONS:
            return CorrelationResult(
                pearson=float("nan"),
                spearman=float("nan"),
                observations=count,
                unavailable_reason=(
                    f"correlation requires at least {MINIMUM_CORRELATION_OBSERVATIONS} "
                    f"aligned observations; {count} available. Three points on any "
                    f"straight line correlate at exactly 1.0, so a small sample "
                    f"reports an artefact rather than a relationship"
                ),
            )
        return CorrelationResult(
            pearson=float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="pearson")),
            spearman=float(aligned.iloc[:, 1].corr(aligned.iloc[:, 0], method="spearman")),
            observations=count,
        )

    @staticmethod
    def rolling_zscore(spread: pd.Series, window: int) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least two")
        rolling_mean = spread.rolling(window=window, min_periods=window).mean()
        rolling_std = spread.rolling(window=window, min_periods=window).std(ddof=0)
        return (spread - rolling_mean) / rolling_std.replace(0, np.nan)

    def rolling_beta(
        self,
        target: pd.Series,
        benchmark: pd.Series,
        window: int,
    ) -> RollingBetaResult:
        if window < 2:
            raise ValueError("window must be at least two")
        aligned = pd.concat([target, benchmark], axis=1).dropna()
        target_returns = aligned.iloc[:, 0].pct_change(fill_method=None)
        benchmark_returns = aligned.iloc[:, 1].pct_change(fill_method=None)
        covariance = benchmark_returns.rolling(window=window, min_periods=window).cov(
            target_returns
        )
        variance = benchmark_returns.rolling(window=window, min_periods=window).var(ddof=1)
        values = (covariance / variance.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        valid = values.dropna()
        positive = int((valid > 0).sum())
        negative = int((valid < 0).sum())
        count = len(valid)
        summary: dict[str, object] = {
            "window": window,
            "valid_windows": count,
            "latest": float(valid.iloc[-1]) if count else None,
            "mean": float(valid.mean()) if count else None,
            "median": float(valid.median()) if count else None,
            "standard_deviation": float(valid.std(ddof=0)) if count else None,
            "minimum": float(valid.min()) if count else None,
            "maximum": float(valid.max()) if count else None,
            "positive_fraction": positive / count if count else None,
            "negative_fraction": negative / count if count else None,
            "sign_consistency": max(positive, negative) / count if count else None,
        }
        return RollingBetaResult(values, summary)

    @staticmethod
    def cointegration_stationarity(
        target: pd.Series,
        benchmark: pd.Series,
        significance_level: float = 0.05,
    ) -> dict[str, object]:
        """Engle-Granger style residual diagnostics for a candidate relationship.

        A two-step procedure regresses the target on the benchmark and applies
        an augmented Dickey-Fuller test to the OLS residuals. A stationary
        residual series is the cointegration evidence. A KPSS test on the same
        residuals is reported alongside it because both tests can reject, and
        disagreement is reported rather than hidden.

        The p-value is the one adjusted for a single cointegrating regressor,
        because the residuals were produced by a regression that contains one.
        The zero-regressor value is also reported, so a reader can see what the
        adjustment changed instead of taking the corrected figure on trust.

        Stationarity testing is a research diagnostic, not evidence of an
        executable edge. A cointegrated pair can still be untradable after
        spread, commission, slippage, and latency.
        """
        if not 0.0 < significance_level < 1.0:
            raise ValueError("significance_level must be between zero and one")
        aligned = pd.concat([target, benchmark], axis=1).dropna()
        observations = len(aligned)
        base: dict[str, object] = {
            "status": "unavailable",
            "unavailable_reason": None,
            "significance_level": significance_level,
            "observations": observations,
            "residual_observations": 0,
            "engle_granger_method": "statsmodels_coint_trend_c_autolag_aic",
            "engle_granger_statistic": None,
            "engle_granger_p_value": None,
            "cointegrated_at_significance": None,
            "adf_method": "statsmodels_coint_autolag_aic_one_cointegrating_regressor",
            "adf_statistic": None,
            "adf_p_value": None,
            "adf_p_value_is_regressor_adjusted": None,
            "adf_p_value_without_regressor_adjustment": None,
            "adf_stationary_at_significance": None,
            "kpss_method": "statsmodels_kpss_level_autolag",
            "kpss_statistic": None,
            "kpss_p_value": None,
            "kpss_p_value_is_bounded": None,
            "kpss_stationary_at_significance": None,
            "stationarity_tests_agree": None,
        }
        if observations < 30:
            base["unavailable_reason"] = (
                f"stationarity tests require at least 30 aligned observations, got {observations}"
            )
            return base
        if np.ptp(aligned.iloc[:, 0]) == 0 or np.ptp(aligned.iloc[:, 1]) == 0:
            base["unavailable_reason"] = "target or benchmark is constant"
            return base
        y = aligned.iloc[:, 0].to_numpy(dtype=float)
        x = aligned.iloc[:, 1].to_numpy(dtype=float)
        try:
            design = np.column_stack([np.ones(len(x)), x])
            coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
            residuals = y - design @ coefficients
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            base["unavailable_reason"] = "ordinary least squares residuals could not be computed"
            return base
        residual_scale = max(1.0, float(np.max(np.abs(y))))
        degenerate_residuals = bool(np.max(np.abs(residuals)) <= 1e-12 * residual_scale)
        if not np.all(np.isfinite(residuals)) or np.ptp(residuals) == 0.0 or degenerate_residuals:
            base["unavailable_reason"] = "residual series is constant or not finite"
            return base

        adf = _engle_granger(y, x, residuals)
        if adf is None:
            if _is_nearly_collinear(y, x):
                base["unavailable_reason"] = (
                    "target and benchmark are nearly collinear, so the cointegration "
                    "test is not numerically reliable"
                )
            else:
                base["unavailable_reason"] = "augmented Dickey-Fuller test could not be computed"
            return base
        adf_stat, adf_p, adf_lag, adf_p_unadjusted = adf
        kpss_result = _kpss_level(residuals)
        if kpss_result is None:
            base["unavailable_reason"] = "KPSS test could not be computed"
            return base
        kpss_stat, kpss_p, kpss_bounded = kpss_result

        adf_stationary = bool(adf_p < significance_level)
        kpss_stationary = bool(kpss_p >= significance_level)
        cointegrated = bool(adf_p < significance_level)
        return {
            **base,
            "status": "available",
            "unavailable_reason": None,
            "residual_observations": len(residuals),
            "adf_lag": adf_lag,
            "engle_granger_statistic": float(adf_stat),
            "engle_granger_p_value": float(adf_p),
            "cointegrated_at_significance": cointegrated,
            "adf_statistic": float(adf_stat),
            "adf_p_value": float(adf_p),
            "adf_p_value_is_regressor_adjusted": True,
            "adf_p_value_without_regressor_adjustment": float(adf_p_unadjusted),
            "adf_stationary_at_significance": adf_stationary,
            "kpss_statistic": float(kpss_stat),
            "kpss_p_value": float(kpss_p),
            "kpss_p_value_is_bounded": kpss_bounded,
            "kpss_stationary_at_significance": kpss_stationary,
            "stationarity_tests_agree": adf_stationary == kpss_stationary,
        }

    def half_life(self, spread: pd.Series) -> HalfLifeResult:
        """Estimate the half-life of a spread, or say why none exists.

        The estimate is `-ln(2) / slope` from regressing the change on the level,
        and a slope near zero makes it diverge, so the old code could report a
        figure like 6e15 on a series that never reverts at all. Two conditions
        now bound it: the sample must be large enough to fit, and the slope must
        be distinguishable from zero. Failing either reports no reversion with
        the reason attached, rather than a number a reader would have to know to
        distrust.

        A separate bound on the resulting half-life was considered and dropped.
        For an AR(1) process the half-life is `ln(0.5)/ln(rho)`, which exceeds
        the sample length only when `rho` is above roughly 0.999, and at that
        coefficient the slope is no longer distinguishable from zero in any
        sample of practical size. The bound could therefore never fire while
        being significant, which would have been a check that always passed and
        gave the impression the extremes were covered.
        """
        values = spread.dropna().to_numpy(dtype=float)
        count = len(values)
        if count < MINIMUM_HALF_LIFE_OBSERVATIONS:
            raise InsufficientDataError(
                f"half-life requires at least {MINIMUM_HALF_LIFE_OBSERVATIONS} observations"
            )
        if np.ptp(values) == 0:
            return HalfLifeResult(
                None,
                False,
                count,
                unavailable_reason="the series is constant, so it has no reversion to measure",
            )
        lagged = values[:-1]
        deltas = np.diff(values)
        regression = stats.linregress(lagged, deltas)
        significant = bool(regression.pvalue < 0.05)
        if not significant:
            return HalfLifeResult(
                None,
                False,
                count,
                unavailable_reason=(
                    f"the regression slope is not distinguishable from zero "
                    f"(p={regression.pvalue:.3f}), so no reversion is demonstrated"
                ),
                regression_is_significant=False,
            )
        if regression.slope >= 0:
            return HalfLifeResult(
                None,
                False,
                count,
                unavailable_reason="the spread is not reverting: the slope is not negative",
                regression_is_significant=True,
            )
        return HalfLifeResult(
            half_life=float(-log(2) / regression.slope),
            mean_reversion=True,
            observations=count,
            regression_is_significant=True,
        )

    @staticmethod
    def lead_lag(
        predictor: pd.Series,
        target: pd.Series,
        max_lag: int,
    ) -> pd.DataFrame:
        """Correlate a predictor against a target across a range of lags.

        **Sign convention.** A positive `lag` means the predictor leads: the
        predictor is shifted forward, so it is compared with the target at a
        later instant. A negative `lag` means the predictor lags. The columns
        `predictor_leads` and `predictor_lags` say the same thing in words,
        because a sign convention that has to be inferred from the code is not a
        convention.

        **Significance.** `significant` and `p_value` come from a two-sided
        test of zero correlation, and a lag with too few aligned observations
        reports `None` rather than a value computed from a handful of points. The
        raw correlation is always reported: a reader deciding for themselves
        should not have to reconstruct it, and a significant-looking correlation
        from four observations should be visible rather than hidden.
        """
        if max_lag < 1:
            raise ValueError("max_lag must be positive")
        results: list[dict[str, float | int | bool | None]] = []
        for lag in range(-max_lag, max_lag + 1):
            shifted = predictor.shift(lag)
            aligned = pd.concat([shifted, target], axis=1).dropna()
            count = len(aligned)
            if count < MINIMUM_LEAD_LAG_OBSERVATIONS:
                results.append(
                    {
                        "lag": lag,
                        "predictor_leads": lag > 0,
                        "predictor_lags": lag < 0,
                        "correlation": float("nan"),
                        "observations": count,
                        "p_value": None,
                        "significant": None,
                        "significant_and_usable": False,
                    }
                )
                continue
            left = aligned.iloc[:, 0]
            right = aligned.iloc[:, 1]
            correlation = float(left.corr(right))
            outcome = stats.pearsonr(left, right)
            p_value = float(outcome.pvalue)
            magnitude = abs(correlation) >= MINIMUM_LEAD_LAG_ABSOLUTE_CORRELATION
            results.append(
                {
                    "lag": lag,
                    "predictor_leads": lag > 0,
                    "predictor_lags": lag < 0,
                    "correlation": correlation,
                    "observations": count,
                    "p_value": p_value,
                    "significant": p_value < 0.05,
                    "significant_and_usable": bool(p_value < 0.05 and magnitude),
                }
            )
        return pd.DataFrame(results)


def _engle_granger(
    target: np.ndarray,
    benchmark: np.ndarray,
    residuals: np.ndarray,
) -> tuple[float, float, int, float] | None:
    """Run the Engle-Granger step 2 test on the regression residuals.

    Returns ``(statistic, p_value, lags, unadjusted_p_value)`` or ``None`` when
    the test cannot be computed.

    Step 2 tests a residual series produced by a regression that contains one
    predetermined regressor, so the p-value must be read from the distribution
    adjusted for that regressor. ``statsmodels.coint`` performs the same
    augmented Dickey-Fuller regression and reports the regressor-adjusted
    p-value; a bare ``adfuller`` call on the residuals uses the
    zero-regressor table, which is anti-conservative by roughly a factor of two
    here and reports near unit-root residuals as stationary. The unadjusted
    value is returned alongside it so the report can state how much the
    adjustment changed the figure.

    ``None`` is returned when the pair is so nearly collinear that ``coint``
    yields a statistic of ``-inf`` with a p-value of zero. That combination is
    a documented numerical artifact rather than a test result, and reporting it
    would claim cointegration for a pair the test could not actually examine.
    """
    if len(residuals) < 12 or not np.all(np.isfinite(residuals)):
        return None
    maxlag = min(int(len(residuals) // 4), 8)
    try:
        unadjusted = adfuller(
            residuals,
            maxlag=maxlag,
            autolag="AIC",
            regression="c",
            result_object=True,
        )
        with warnings.catch_warnings():
            # A collinear pair is reported as an unavailable result by the
            # caller, not as console noise.
            warnings.filterwarnings("ignore", category=CollinearityWarning)
            result = coint(target, benchmark, trend="c", maxlag=maxlag, autolag="aic")
    except (
        ValueError,
        np.linalg.LinAlgError,
        ZeroDivisionError,
        FloatingPointError,
        MissingDataError,
    ):
        return None
    statistic = float(result[0])
    p_value = float(result[1])
    unadjusted_p_value = float(unadjusted.pvalue)
    if not np.isfinite(statistic) or not np.isfinite(p_value):
        return None
    if not np.isfinite(unadjusted_p_value):
        unadjusted_p_value = float("nan")
    return statistic, p_value, int(unadjusted.lags), unadjusted_p_value


def _is_nearly_collinear(target: np.ndarray, benchmark: np.ndarray) -> bool:
    """Return whether the benchmark explains the target almost exactly.

    ``statsmodels.coint`` signals this case with a statistic of ``-inf`` and a
    p-value of zero, which it documents as numerically unstable rather than as
    a test outcome. Reporting that zero as cointegration evidence would claim a
    result the test never produced, so the caller reports the pair as
    unavailable and names collinearity as the reason.

    The criterion matches the one ``coint`` applies, so this detects the
    condition that made the test unusable rather than a stricter one of its
    own: a near-perfect fit at ``1 - 100 * sqrt(eps)`` or above.
    """
    try:
        design = np.column_stack([np.ones(len(benchmark)), benchmark])
        coefficients, residuals, _, _ = np.linalg.lstsq(design, target, rcond=None)
    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
        return False
    residual_sum = (
        float(np.sum(residuals**2))
        if residuals.size
        else float(np.sum((target - design @ coefficients) ** 2))
    )
    total_sum = float(np.sum((target - float(np.mean(target))) ** 2))
    if total_sum <= 0.0:
        return False
    r_squared = 1.0 - residual_sum / total_sum
    return bool(r_squared >= 1.0 - 100.0 * math.sqrt(np.finfo(float).eps))


def _kpss_level(values: np.ndarray) -> tuple[float, float, bool] | None:
    """Run a KPSS level-stationarity test.

    Returns ``(statistic, p_value, p_value_is_bounded)``. The KPSS p-value is
    bounded below by the lookup table, so a bounded result is surfaced to the
    caller instead of being presented as an exact probability.
    """
    if len(values) < 12 or not np.all(np.isfinite(values)):
        return None
    try:
        with warnings.catch_warnings():
            # The lookup table bounds the p-value at its floor. The bounded
            # result is returned to the caller and reported as
            # ``kpss_p_value_is_bounded`` instead of being left as console noise.
            warnings.filterwarnings("ignore", category=InterpolationWarning)
            result = kpss(values, regression="c", nlags="auto", result_object=True)
    except (ValueError, np.linalg.LinAlgError, ZeroDivisionError, FloatingPointError):
        return None
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not np.isfinite(statistic) or not np.isfinite(p_value):
        return None
    return statistic, p_value, bool(p_value <= 0.01)
