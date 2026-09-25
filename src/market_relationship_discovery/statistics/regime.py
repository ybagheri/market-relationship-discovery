from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd


class Regime(StrEnum):
    LOW_VOLATILITY = "low_volatility"
    NORMAL_VOLATILITY = "normal_volatility"
    HIGH_VOLATILITY = "high_volatility"


@dataclass(frozen=True, slots=True)
class RegimeDetectionResult:
    labels: pd.Series
    rolling_volatility: pd.Series
    lower_threshold: pd.Series
    upper_threshold: pd.Series

    def summary(self) -> dict[str, object]:
        counts = self.labels.value_counts(dropna=True)
        total = int(counts.sum())
        return {
            "observations": total,
            "counts": {str(regime): int(counts.get(regime.value, 0)) for regime in Regime},
            "fractions": {
                regime.value: float(counts.get(regime.value, 0) / total) if total else 0.0
                for regime in Regime
            },
            "warmup_observations": int(self.labels.isna().sum()),
        }


class RegimeDetector:
    def detect(
        self,
        prices: pd.Series,
        *,
        window: int = 20,
        low_quantile: float = 0.20,
        high_quantile: float = 0.80,
    ) -> RegimeDetectionResult:
        if window < 2:
            raise ValueError("window must be at least two")
        if not 0.0 <= low_quantile < high_quantile <= 1.0:
            raise ValueError("quantiles must satisfy 0 <= low < high <= 1")
        numeric = pd.to_numeric(prices, errors="raise").astype(float)
        if numeric.isna().any() or (numeric <= 0).any():
            raise ValueError("prices must be finite positive values")
        returns = np.log(numeric).diff()
        volatility = returns.rolling(window=window, min_periods=window).std(ddof=0)
        lower = volatility.expanding(min_periods=1).quantile(low_quantile)
        upper = volatility.expanding(min_periods=1).quantile(high_quantile)
        labels = pd.Series(pd.NA, index=prices.index, dtype="object")
        valid = volatility.notna() & lower.notna() & upper.notna()
        constant = volatility.notna() & (volatility == 0)
        degenerate = valid & (lower == upper)
        normal = valid & ~constant & (degenerate | ((volatility > lower) & (volatility < upper)))
        high = valid & ~constant & ~degenerate & (volatility >= upper)
        low = valid & ~constant & ~degenerate & (volatility <= lower)
        labels.loc[normal] = Regime.NORMAL_VOLATILITY.value
        labels.loc[high] = Regime.HIGH_VOLATILITY.value
        labels.loc[low] = Regime.LOW_VOLATILITY.value
        labels.loc[constant] = Regime.NORMAL_VOLATILITY.value
        return RegimeDetectionResult(labels, volatility, lower, upper)
