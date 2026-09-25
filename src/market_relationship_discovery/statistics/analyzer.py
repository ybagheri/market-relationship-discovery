from dataclasses import dataclass
from math import log

import numpy as np
import pandas as pd
from scipy import stats

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
        if not 0.0 < significance_level < 1.0:
            raise ValueError("significance_level must be between zero and one")
        aligned = pd.concat([target, benchmark], axis=1).dropna()
        observations = len(aligned)
        base: dict[str, object] = {
            "status": "unavailable",
            "significance_level": significance_level,
            "observations": observations,
            "residual_observations": 0,
            "engle_granger_method": "ols_residual_adf_approximation",
            "engle_granger_statistic": None,
            "engle_granger_p_value": None,
            "cointegrated_at_significance": None,
            "adf_method": "fixed_lag1_ols_normal_approximation",
            "adf_statistic": None,
            "adf_p_value": None,
            "adf_stationary_at_significance": None,
            "kpss_method": "level_cusum_chi_square_approximation",
            "kpss_statistic": None,
            "kpss_p_value": None,
            "kpss_stationary_at_significance": None,
            "stationarity_tests_agree": None,
        }
        if observations < 8 or np.ptp(aligned.iloc[:, 0]) == 0 or np.ptp(aligned.iloc[:, 1]) == 0:
            return base
        y = aligned.iloc[:, 0].to_numpy(dtype=float)
        x = aligned.iloc[:, 1].to_numpy(dtype=float)
        try:
            design = np.column_stack([np.ones(len(x)), x])
            coefficients, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
            residuals = y - design @ coefficients
            adf_stat, adf_p = _adf_approximation(residuals)
            kpss_stat, kpss_p = _kpss_approximation(residuals)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return base
        engle_stat, engle_p = adf_stat, adf_p
        adf_stationary = bool(adf_p < significance_level)
        kpss_stationary = bool(kpss_p >= significance_level)
        return {
            **base,
            "status": "available",
            "residual_observations": len(residuals),
            "engle_granger_statistic": float(engle_stat),
            "engle_granger_p_value": float(engle_p),
            "cointegrated_at_significance": bool(engle_p < significance_level),
            "adf_statistic": float(adf_stat),
            "adf_p_value": float(adf_p),
            "adf_stationary_at_significance": adf_stationary,
            "kpss_statistic": float(kpss_stat),
            "kpss_p_value": float(kpss_p),
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


def _adf_approximation(values: np.ndarray) -> tuple[float, float]:
    if len(values) < 8:
        raise ValueError("ADF approximation requires at least eight observations")
    if np.allclose(values, 0.0):
        return -1e308, 0.0
    level = values[1:]
    lagged = values[:-1]
    changes = np.diff(values)
    design = np.column_stack([np.ones(len(changes)), level, lagged])
    coefficients, _, _, _ = np.linalg.lstsq(design, changes, rcond=None)
    residuals = changes - design @ coefficients
    degrees_of_freedom = len(changes) - design.shape[1]
    if degrees_of_freedom <= 0:
        raise ValueError("ADF approximation has no residual degrees of freedom")
    covariance = np.linalg.inv(design.T @ design) * (
        float(residuals @ residuals) / degrees_of_freedom
    )
    standard_error = float(np.sqrt(covariance[1, 1]))
    if standard_error == 0.0:
        return float("-inf" if coefficients[1] < 0 else "inf"), 0.0
    statistic = float(coefficients[1] / standard_error)
    p_value = float(2.0 * stats.norm.sf(abs(statistic) / np.sqrt(2.0)))
    return statistic, p_value


def _kpss_approximation(values: np.ndarray) -> tuple[float, float]:
    if len(values) < 8:
        raise ValueError("KPSS approximation requires at least eight observations")
    centered = values - float(values.mean())
    long_run_variance = float(np.var(centered, ddof=0))
    if long_run_variance == 0.0:
        return 0.0, 1.0
    cumulative = np.cumsum(centered)
    statistic = float(cumulative @ cumulative / (len(values) ** 2 * long_run_variance))
    p_value = float(stats.chi2.sf(statistic, df=1))
    return statistic, p_value
