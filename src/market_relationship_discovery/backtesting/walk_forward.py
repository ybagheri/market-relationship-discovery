from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

from market_relationship_discovery.backtesting.engine import (
    BacktestMetrics,
    NoLookAheadTrade,
    ResearchBacktester,
)
from market_relationship_discovery.domain.errors import InsufficientDataError


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    train_observations: int
    validation_observations: int
    test_observations: int
    step_observations: int | None = None
    thresholds: tuple[float, ...] = (0.0,)
    minimum_train_observations: int = 1


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    window: WalkForwardWindow
    status: str
    selected_threshold: float | None
    selection_score: float | None
    train_metrics: BacktestMetrics
    validation_metrics: BacktestMetrics
    test_metrics: BacktestMetrics
    test_trades: tuple[NoLookAheadTrade, ...]


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    folds: tuple[WalkForwardFold, ...]
    aggregate_test_metrics: BacktestMetrics
    completed_folds: int


class WalkForwardSplitter:
    def __init__(self, config: WalkForwardConfig) -> None:
        if (
            min(
                config.train_observations,
                config.validation_observations,
                config.test_observations,
            )
            < 1
        ):
            raise ValueError("walk-forward window sizes must be positive")
        step = config.step_observations or config.test_observations
        if step < 1:
            raise ValueError("step_observations must be positive")
        self._config = config
        self._step = step

    def split(self, index: pd.DatetimeIndex) -> tuple[WalkForwardWindow, ...]:
        if not isinstance(index, pd.DatetimeIndex):
            raise TypeError("walk-forward requires a DatetimeIndex")
        if index.hasnans or not index.is_monotonic_increasing or index.has_duplicates:
            raise ValueError("walk-forward index must be sorted, unique, and timezone-aware")
        required = (
            self._config.train_observations
            + self._config.validation_observations
            + self._config.test_observations
        )
        windows: list[WalkForwardWindow] = []
        start = 0
        fold = 1
        while start + required <= len(index):
            train_start = start
            train_end = start + self._config.train_observations - 1
            validation_start = train_end + 1
            validation_end = validation_start + self._config.validation_observations - 1
            test_start = validation_end + 1
            test_end = test_start + self._config.test_observations - 1
            windows.append(
                WalkForwardWindow(
                    fold=fold,
                    train_start=index[train_start],
                    train_end=index[train_end],
                    validation_start=index[validation_start],
                    validation_end=index[validation_end],
                    test_start=index[test_start],
                    test_end=index[test_end],
                )
            )
            start += self._step
            fold += 1
        return tuple(windows)

    def slices(
        self,
        frame: pd.DataFrame,
        window: WalkForwardWindow,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        train = frame.loc[window.train_start : window.train_end]
        validation = frame.loc[window.validation_start : window.validation_end]
        test = frame.loc[window.test_start : window.test_end]
        return train, validation, test


class WalkForwardValidator:
    def __init__(self) -> None:
        self._backtester = ResearchBacktester()
        self._splitter = WalkForwardSplitter

    def run(
        self,
        frame: pd.DataFrame,
        config: WalkForwardConfig,
        signal_column: str,
        gross_edge_column: str,
        cost_column: str,
    ) -> WalkForwardResult:
        required = {signal_column, gross_edge_column, cost_column}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"walk-forward data is missing columns: {sorted(missing)}")
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise TypeError("walk-forward requires a DatetimeIndex")
        splitter = self._splitter(config)
        windows = splitter.split(frame.index)
        if not windows:
            raise InsufficientDataError("not enough observations for one walk-forward fold")
        folds: list[WalkForwardFold] = []
        for window in windows:
            folds.append(
                self._run_fold(
                    splitter,
                    frame,
                    window,
                    config,
                    signal_column,
                    gross_edge_column,
                    cost_column,
                )
            )
        completed = tuple(fold for fold in folds if fold.status == "completed")
        test_trades = tuple(
            trade
            for fold in completed
            for trade in sorted(
                fold.test_trades,
                key=lambda item: str(item.execution_timestamp),
            )
        )
        return WalkForwardResult(
            folds=tuple(folds),
            aggregate_test_metrics=self._backtester.summarize_trades(test_trades),
            completed_folds=len(completed),
        )

    def _run_fold(
        self,
        splitter: WalkForwardSplitter,
        frame: pd.DataFrame,
        window: WalkForwardWindow,
        config: WalkForwardConfig,
        signal_column: str,
        gross_edge_column: str,
        cost_column: str,
    ) -> WalkForwardFold:
        train, validation, test = splitter.slices(frame, window)
        candidates: list[tuple[float, float, BacktestMetrics]] = []
        for threshold in sorted(set(config.thresholds)):
            if not isfinite(threshold):
                continue
            result = self._backtester.run_next_observation(
                pd.to_numeric(train[signal_column], errors="raise") > threshold,
                pd.to_numeric(train[gross_edge_column], errors="raise"),
                pd.to_numeric(train[cost_column], errors="raise"),
            )
            if result.metrics.observations >= config.minimum_train_observations:
                score = result.metrics.average_return
                if score is not None:
                    candidates.append((score, threshold, result.metrics))
        if not candidates:
            empty = self._backtester.summarize_trades(())
            return WalkForwardFold(
                window=window,
                status="insufficient_train_observations",
                selected_threshold=None,
                selection_score=None,
                train_metrics=empty,
                validation_metrics=empty,
                test_metrics=empty,
                test_trades=(),
            )
        score, threshold, train_metrics = min(candidates, key=lambda item: (-item[0], item[1]))
        validation_result = self._backtester.run_next_observation(
            pd.to_numeric(validation[signal_column], errors="raise") > threshold,
            pd.to_numeric(validation[gross_edge_column], errors="raise"),
            pd.to_numeric(validation[cost_column], errors="raise"),
        )
        test_result = self._backtester.run_next_observation(
            pd.to_numeric(test[signal_column], errors="raise") > threshold,
            pd.to_numeric(test[gross_edge_column], errors="raise"),
            pd.to_numeric(test[cost_column], errors="raise"),
        )
        return WalkForwardFold(
            window=window,
            status="completed",
            selected_threshold=threshold,
            selection_score=score,
            train_metrics=train_metrics,
            validation_metrics=validation_result.metrics,
            test_metrics=test_result.metrics,
            test_trades=test_result.trades,
        )
