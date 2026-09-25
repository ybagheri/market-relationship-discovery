from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite

import pandas as pd

from market_relationship_discovery.domain.errors import InsufficientDataError
from market_relationship_discovery.relationships.catalog import RelationshipDefinition
from market_relationship_discovery.relationships.formula import Expression, FormulaParser, Operation
from market_relationship_discovery.statistics.analyzer import StatisticalAnalyzer


@dataclass(frozen=True, slots=True)
class ResearchSummary:
    relationship: str
    target: str
    formula: str
    classification: str
    observations: int
    start: datetime | None
    end: datetime | None
    mean_discrepancy: float
    discrepancy_std: float
    maximum_absolute_discrepancy: float
    pearson_correlation: float
    spearman_correlation: float
    latest_zscore: float | None
    half_life: float | None
    beta_stability: dict[str, object]
    cointegration_stationarity: dict[str, object]
    executable_discrepancy_claimed: bool = False

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["start"] = self.start.isoformat() if self.start else None
        result["end"] = self.end.isoformat() if self.end else None
        return result


class HistoricalRelationshipResearcher:
    def __init__(
        self,
        max_alignment_delay_ms: int,
        zscore_window: int,
        minimum_observations: int,
        rolling_beta_window: int = 30,
        statistical_significance: float = 0.05,
    ) -> None:
        self._max_alignment_delay_ms = max_alignment_delay_ms
        self._zscore_window = zscore_window
        self._minimum_observations = minimum_observations
        self._rolling_beta_window = rolling_beta_window
        self._statistical_significance = statistical_significance
        self._statistics = StatisticalAnalyzer()

    def run(
        self,
        relationship: RelationshipDefinition,
        series: dict[str, pd.DataFrame],
    ) -> ResearchSummary:
        aligned = self._align(relationship, series)
        if len(aligned) < self._minimum_observations:
            raise InsufficientDataError(
                f"{relationship.name} requires {self._minimum_observations} aligned observations; "
                f"received {len(aligned)}"
            )
        expression = FormulaParser.parse(relationship.formula)
        theoretical = [
            self._evaluate(
                expression,
                {symbol: float(row[symbol]) for symbol in aligned.columns[1:]},
            )
            for _, row in aligned.iterrows()
        ]
        actual = aligned[relationship.target].astype(float)
        synthetic = pd.Series(theoretical, index=aligned.index, dtype=float)
        discrepancy = actual - synthetic
        correlation = self._statistics.correlation(actual, synthetic)
        zscore = self._statistics.rolling_zscore(discrepancy, self._zscore_window)
        try:
            half_life = self._statistics.half_life(discrepancy).half_life
        except InsufficientDataError:
            half_life = None
        beta_stability = self._statistics.rolling_beta(
            actual,
            synthetic,
            self._rolling_beta_window,
        ).summary
        cointegration_stationarity = self._statistics.cointegration_stationarity(
            actual,
            synthetic,
            self._statistical_significance,
        )
        latest_zscore = float(zscore.iloc[-1]) if isfinite(zscore.iloc[-1]) else None
        return ResearchSummary(
            relationship=relationship.name,
            target=relationship.target,
            formula=relationship.formula,
            classification="requires_further_validation",
            observations=len(aligned),
            start=aligned.index[0].to_pydatetime(),
            end=aligned.index[-1].to_pydatetime(),
            mean_discrepancy=float(discrepancy.mean()),
            discrepancy_std=float(discrepancy.std(ddof=0)),
            maximum_absolute_discrepancy=float(discrepancy.abs().max()),
            pearson_correlation=correlation.pearson,
            spearman_correlation=correlation.spearman,
            latest_zscore=latest_zscore,
            half_life=half_life,
            beta_stability=beta_stability,
            cointegration_stationarity=cointegration_stationarity,
        )

    def _align(
        self,
        relationship: RelationshipDefinition,
        series: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        required = set(relationship.dependencies()) | {relationship.target}
        missing = required - set(series)
        if missing:
            raise ValueError(f"missing symbol series: {sorted(missing)}")
        target_frame = self._close_series(series[relationship.target])
        result = target_frame.rename(columns={"close": relationship.target})
        for symbol in sorted(relationship.dependencies()):
            right = self._close_series(series[symbol]).rename(columns={"close": symbol})
            right = right.assign(_right_timestamp=right["timestamp"])
            merged = pd.merge_asof(
                result.sort_index(),
                right.sort_index(),
                left_on="timestamp",
                right_on="timestamp",
                direction="backward",
                tolerance=pd.Timedelta(milliseconds=self._max_alignment_delay_ms),
            )
            merged[f"{symbol}_alignment_delay_ms"] = (
                merged["timestamp"] - merged["_right_timestamp"]
            ).dt.total_seconds() * 1000.0
            result = merged.drop(columns=["_right_timestamp"])
        result = result.dropna(subset=list(required)).set_index("timestamp")
        return result.sort_index()

    @staticmethod
    def _close_series(frame: pd.DataFrame) -> pd.DataFrame:
        if not {"timestamp", "close"}.issubset(frame.columns):
            raise ValueError("series require timestamp and close columns")
        result = frame[["timestamp", "close"]].copy()
        result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
        if result["timestamp"].duplicated().any():
            raise ValueError("series contain duplicate timestamps")
        return result.sort_values("timestamp")

    def _evaluate(self, expression: Expression, values: dict[str, float]) -> float:
        if expression.symbol is not None:
            return values[expression.symbol]
        if expression.left is None or expression.right is None or expression.operation is None:
            raise ValueError("invalid formula expression")
        left = self._evaluate(expression.left, values)
        right = self._evaluate(expression.right, values)
        match expression.operation:
            case Operation.ADD:
                return left + right
            case Operation.SUBTRACT:
                return left - right
            case Operation.MULTIPLY:
                return left * right
            case Operation.DIVIDE:
                if right == 0:
                    raise ValueError("division denominator is zero")
                return left / right
        raise ValueError(f"unsupported operation: {expression.operation}")
