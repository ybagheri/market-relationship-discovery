from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from market_relationship_discovery.backtesting.multi_stage import CausalFeatureBuilder
from market_relationship_discovery.discovery.engine import CandidateStatus, DiscoveryCandidate
from market_relationship_discovery.domain.errors import DataQualityError
from market_relationship_discovery.relationships.formula import Expression, FormulaParser
from market_relationship_discovery.statistics.analyzer import StatisticalAnalyzer
from market_relationship_discovery.statistics.regime import RegimeDetector


@dataclass(frozen=True, slots=True)
class EvaluatedCandidate:
    candidate: DiscoveryCandidate
    frame: pd.DataFrame
    summary: dict[str, object]


class GraphCandidateEvaluator:
    def evaluate(
        self,
        prices: pd.DataFrame,
        candidates: list[DiscoveryCandidate],
        *,
        minimum_observations: int = 30,
        regime_window: int = 20,
        regime_low_quantile: float = 0.20,
        regime_high_quantile: float = 0.80,
        rolling_beta_window: int = 30,
        statistical_significance: float = 0.05,
    ) -> list[EvaluatedCandidate]:
        if minimum_observations < 3:
            raise ValueError("minimum_observations must be at least three")
        return [
            self._evaluate_candidate(
                prices,
                candidate,
                minimum_observations,
                regime_window,
                regime_low_quantile,
                regime_high_quantile,
                rolling_beta_window,
                statistical_significance,
            )
            for candidate in candidates
        ]

    def _evaluate_candidate(
        self,
        prices: pd.DataFrame,
        candidate: DiscoveryCandidate,
        minimum_observations: int,
        regime_window: int,
        regime_low_quantile: float,
        regime_high_quantile: float,
        rolling_beta_window: int,
        statistical_significance: float,
    ) -> EvaluatedCandidate:
        required = {candidate.target, *FormulaParser.parse(candidate.formula).dependencies()}
        missing = required - set(prices.columns)
        if missing:
            return EvaluatedCandidate(
                replace(candidate, status=CandidateStatus.REQUIRES_DATA),
                pd.DataFrame(),
                {
                    "status": CandidateStatus.REQUIRES_DATA.value,
                    "observations": 0,
                    "missing_symbols": sorted(missing),
                },
            )
        actual = pd.to_numeric(prices[candidate.target], errors="raise")
        expression = FormulaParser.parse(candidate.formula)
        synthetic = _evaluate_expression(expression, prices)
        valid = actual.notna() & synthetic.notna() & np.isfinite(synthetic)
        actual = actual.loc[valid]
        synthetic = synthetic.loc[valid]
        if len(actual) < minimum_observations:
            return EvaluatedCandidate(
                replace(
                    candidate,
                    status=CandidateStatus.INSUFFICIENT_OBSERVATIONS,
                    observations=len(actual),
                ),
                pd.DataFrame(),
                {
                    "status": CandidateStatus.INSUFFICIENT_OBSERVATIONS.value,
                    "observations": len(actual),
                    "minimum_observations": minimum_observations,
                },
            )
        discrepancy = actual - synthetic
        analyzer = StatisticalAnalyzer()
        try:
            correlation = analyzer.correlation(actual, synthetic)
            pearson = correlation.pearson
            spearman = correlation.spearman
        except (ValueError, np.linalg.LinAlgError):
            pearson = float("nan")
            spearman = float("nan")
        try:
            half_life = analyzer.half_life(discrepancy).half_life
        except (ValueError, np.linalg.LinAlgError):
            half_life = None
        rolling_beta = analyzer.rolling_beta(actual, synthetic, rolling_beta_window)
        cointegration = analyzer.cointegration_stationarity(
            actual,
            synthetic,
            statistical_significance,
        )
        zscore = CausalFeatureBuilder.rolling_zscore(discrepancy, min(20, len(discrepancy)))
        zscore = zscore.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        discrepancy_volatility = (
            discrepancy.rolling(window=20, min_periods=5).std(ddof=0).fillna(0.0)
        )
        regime = RegimeDetector().detect(
            actual,
            window=regime_window,
            low_quantile=regime_low_quantile,
            high_quantile=regime_high_quantile,
        )
        history = pd.DataFrame(
            {
                "timestamp": actual.index,
                "actual": actual.to_numpy(),
                "synthetic": synthetic.to_numpy(),
                "discrepancy": discrepancy.to_numpy(),
                "abs_discrepancy": discrepancy.abs().to_numpy(),
                "zscore": zscore.to_numpy(),
                "discrepancy_volatility": discrepancy_volatility.to_numpy(),
                "rolling_beta": rolling_beta.values.reindex(actual.index).to_numpy(),
                "regime": regime.labels.reindex(actual.index).fillna("unknown").to_numpy(),
                "next_abs_zscore": zscore.abs().shift(-1).to_numpy(),
            },
            index=actual.index,
        )
        mean_absolute_discrepancy = float(discrepancy.abs().mean())
        rmse = float(np.sqrt(np.mean(np.square(discrepancy))))
        summary: dict[str, object] = {
            "status": CandidateStatus.REQUIRES_FURTHER_VALIDATION.value,
            "observations": len(history),
            "pearson": pearson,
            "spearman": spearman,
            "half_life": half_life,
            "mean_absolute_discrepancy": mean_absolute_discrepancy,
            "rmse": rmse,
            "p95_absolute_discrepancy": float(discrepancy.abs().quantile(0.95)),
            "latest_zscore": float(zscore.iloc[-1]),
            "regime_counts": regime.summary()["counts"],
            "beta_stability": rolling_beta.summary,
            "cointegration_stationarity": cointegration,
        }
        return EvaluatedCandidate(
            replace(
                candidate,
                status=CandidateStatus.REQUIRES_FURTHER_VALIDATION,
                observations=len(history),
                metrics={
                    "pearson": float(pearson),
                    "spearman": float(spearman),
                    "mean_absolute_discrepancy": mean_absolute_discrepancy,
                    "rmse": rmse,
                },
            ),
            history,
            summary,
        )


def _evaluate_expression(expression: Expression, prices: pd.DataFrame) -> pd.Series:
    if expression.symbol is not None:
        return pd.to_numeric(prices[expression.symbol], errors="raise")
    if expression.left is None or expression.right is None:
        raise DataQualityError("invalid formula expression")
    left = _evaluate_expression(expression.left, prices)
    right = _evaluate_expression(expression.right, prices)
    operation = expression.operation
    if operation is None:
        raise DataQualityError("formula expression has no operation")
    match operation.value:
        case "add":
            return left + right
        case "subtract":
            return left - right
        case "multiply":
            return left * right
        case "divide":
            if (right == 0).any():
                raise DataQualityError("formula denominator cannot be zero")
            return left / right
        case _:
            raise DataQualityError("unsupported formula operation")
