from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from market_relationship_discovery.backtesting.engine import (
    NoLookAheadResult,
    ResearchBacktester,
)


@dataclass(frozen=True, slots=True)
class SignalStage:
    name: str
    column: str
    weight: float = 1.0
    activation_threshold: float = 0.0


@dataclass(frozen=True, slots=True)
class MultiStageResult:
    ensemble: NoLookAheadResult
    stages: dict[str, NoLookAheadResult]
    stage_weights: dict[str, float]
    activation_threshold: float


class CausalFeatureBuilder:
    @staticmethod
    def rolling_zscore(values: pd.Series, window: int) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least two")
        mean = values.rolling(window=window, min_periods=window).mean()
        deviation = values.rolling(window=window, min_periods=window).std(ddof=0)
        return (values - mean) / deviation.replace(0, float("nan"))

    @staticmethod
    def momentum(values: pd.Series, lookback: int) -> pd.Series:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        return values.pct_change(periods=lookback)

    @staticmethod
    def realized_volatility(values: pd.Series, window: int) -> pd.Series:
        if window < 2:
            raise ValueError("window must be at least two")
        return values.pct_change().rolling(window=window, min_periods=window).std(ddof=0)


class MultiStageBacktester:
    def __init__(self) -> None:
        self._backtester = ResearchBacktester()

    def run(
        self,
        frame: pd.DataFrame,
        stages: tuple[SignalStage, ...],
        gross_edge_column: str,
        cost_column: str,
        ensemble_threshold: float = 0.0,
    ) -> MultiStageResult:
        if not stages:
            raise ValueError("at least one signal stage is required")
        if frame.index.has_duplicates:
            raise ValueError("backtest timestamps must be unique")
        columns = {stage.column for stage in stages}
        required = columns | {gross_edge_column, cost_column}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"multi-stage backtest is missing columns: {sorted(missing)}")
        stage_values = {
            stage.name: pd.to_numeric(frame[stage.column], errors="raise") for stage in stages
        }
        if len(stage_values) != len(stages):
            raise ValueError("signal stage names must be unique")
        gross_edges = pd.to_numeric(frame[gross_edge_column], errors="raise")
        costs = pd.to_numeric(frame[cost_column], errors="raise")
        if (costs.dropna() < 0).any():
            raise ValueError("costs cannot be negative")
        combined = pd.Series(0.0, index=frame.index)
        for stage in stages:
            combined = combined + stage.weight * stage_values[stage.name]
        ensemble = self._backtester.run_next_observation(
            combined > ensemble_threshold,
            gross_edges,
            costs,
        )
        stage_results = {
            stage.name: self._backtester.run_next_observation(
                stage_values[stage.name] > stage.activation_threshold,
                gross_edges,
                costs,
            )
            for stage in stages
        }
        return MultiStageResult(
            ensemble=ensemble,
            stages=stage_results,
            stage_weights={stage.name: stage.weight for stage in stages},
            activation_threshold=ensemble_threshold,
        )
