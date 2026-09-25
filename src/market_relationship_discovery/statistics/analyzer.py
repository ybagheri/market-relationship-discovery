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

    def half_life(self, spread: pd.Series) -> HalfLifeResult:
        values = spread.dropna().to_numpy(dtype=float)
        if len(values) < 3:
            raise InsufficientDataError("half-life requires at least three observations")
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
