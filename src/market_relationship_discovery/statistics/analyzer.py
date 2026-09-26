import warnings
from dataclasses import dataclass
from math import log

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss

from market_relationship_discovery.domain.errors import InsufficientDataError


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    pearson: float
    spearman: float
    observations: int


@dataclass(frozen=True, slots=True)
class HalfLifeResult:
    half_life: float | None
    mean_reversion: bool
    observations: int


@dataclass(frozen=True, slots=True)
class RollingBetaResult:
    values: pd.Series
    summary: dict[str, object]


class StatisticalAnalyzer:
    def correlation(self, left: pd.Series, right: pd.Series) -> CorrelationResult:
        aligned = pd.concat([left, right], axis=1).dropna()
        if len(aligned) < 3:
            raise InsufficientDataError("correlation requires at least three observations")
        return CorrelationResult(
            pearson=float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="pearson")),
            spearman=float(aligned.iloc[:, 1].corr(aligned.iloc[:, 0], method="spearman")),
            observations=len(aligned),
        )

    @staticmethod
    def rolling_zscore(spread: pd.Series, window: int) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least two")
        rolling_mean = spread.rolling(window=window, min_periods=window).mean()
        rolling_std = spread.rolling(window=window, min_periods=window).std(ddof=0)
        return (spread - rolling_mean) / rolling_std.replace(0, np.nan)

    @staticmethod
    def rolling_correlation(left: pd.Series, right: pd.Series, window: int) -> pd.Series:
        return left.rolling(window=window, min_periods=window).corr(right)

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
            "engle_granger_method": "ols_residual_augmented_dickey_fuller",
            "engle_granger_statistic": None,
            "engle_granger_p_value": None,
            "cointegrated_at_significance": None,
            "adf_method": "statsmodels_adfuller_autolag_aic",
            "adf_statistic": None,
            "adf_p_value": None,
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
        if not np.all(np.isfinite(residuals)) or np.ptp(residuals) == 0.0:
            base["unavailable_reason"] = "residual series is constant or not finite"
            return base

        adf = _augmented_dickey_fuller(residuals)
        if adf is None:
            base["unavailable_reason"] = "augmented Dickey-Fuller test could not be computed"
            return base
        adf_stat, adf_p, adf_lag = adf
        kpss_result = _kpss_level(residuals)
        if kpss_result is None:
            base["unavailable_reason"] = "KPSS test could not be computed"
            return base
        kpss_stat, kpss_p, kpss_bounded = kpss_result

        adf_stationary = bool(adf_p < significance_level)
        kpss_stationary = bool(kpss_p >= significance_level)
        return {
            **base,
            "status": "available",
            "unavailable_reason": None,
            "residual_observations": len(residuals),
            "adf_lag": adf_lag,
            "engle_granger_statistic": float(adf_stat),
            "engle_granger_p_value": float(adf_p),
            "cointegrated_at_significance": bool(adf_p < significance_level),
            "adf_statistic": float(adf_stat),
            "adf_p_value": float(adf_p),
            "adf_stationary_at_significance": adf_stationary,
            "kpss_statistic": float(kpss_stat),
            "kpss_p_value": float(kpss_p),
            "kpss_p_value_is_bounded": kpss_bounded,
            "kpss_stationary_at_significance": kpss_stationary,
            "stationarity_tests_agree": adf_stationary == kpss_stationary,
        }

    def half_life(self, spread: pd.Series) -> HalfLifeResult:
        values = spread.dropna().to_numpy(dtype=float)
        if len(values) < 3:
            raise InsufficientDataError("half-life requires at least three observations")
        if np.ptp(values) == 0:
            return HalfLifeResult(None, False, len(values))
        lagged = values[:-1]
        deltas = np.diff(values)
        regression = stats.linregress(lagged, deltas)
        half_life_value = -log(2) / regression.slope if regression.slope < 0 else None
        return HalfLifeResult(
            half_life=half_life_value,
            mean_reversion=half_life_value is not None,
            observations=len(values),
        )

    @staticmethod
    def lead_lag(
        predictor: pd.Series,
        target: pd.Series,
        max_lag: int,
    ) -> pd.DataFrame:
        if max_lag < 1:
            raise ValueError("max_lag must be positive")
        results: list[dict[str, float | int]] = []
        for lag in range(-max_lag, max_lag + 1):
            shifted = predictor.shift(lag)
            aligned = pd.concat([shifted, target], axis=1).dropna()
            correlation = (
                float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])) if len(aligned) else float("nan")
            )
            results.append({"lag": lag, "correlation": correlation, "observations": len(aligned)})
        return pd.DataFrame(results)


def _augmented_dickey_fuller(values: np.ndarray) -> tuple[float, float, int] | None:
    """Run a constant-only augmented Dickey-Fuller test with automatic lag choice.

    Returns ``(statistic, p_value, lags)`` or ``None`` when the test cannot be
    computed. The test's own p-value and critical values are used rather than a
    hand-rolled normal approximation, because the OLS residuals of a near
    unit-root pair make the regression design badly conditioned and an
    approximate p-value can report a confident false positive.
    """
    if len(values) < 12 or not np.all(np.isfinite(values)):
        return None
    try:
        result = adfuller(
            values,
            maxlag=min(int(len(values) // 4), 8),
            autolag="AIC",
            regression="c",
            result_object=True,
        )
    except (ValueError, np.linalg.LinAlgError, ZeroDivisionError, FloatingPointError):
        return None
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not np.isfinite(statistic) or not np.isfinite(p_value):
        return None
    return statistic, p_value, int(result.lags)


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
