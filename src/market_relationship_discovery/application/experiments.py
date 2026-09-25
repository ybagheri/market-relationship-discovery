from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from market_relationship_discovery.backtesting.engine import ResearchBacktester
from market_relationship_discovery.backtesting.multi_stage import (
    MultiStageBacktester,
    SignalStage,
)
from market_relationship_discovery.backtesting.walk_forward import (
    WalkForwardConfig,
    WalkForwardValidator,
)
from market_relationship_discovery.domain.experiment import create_experiment_manifest
from market_relationship_discovery.reporting.experiment import ExperimentReportWriter


@dataclass(frozen=True, slots=True)
class ResearchDataset:
    source_path: Path
    frame: pd.DataFrame

    @classmethod
    def load(cls, path: Path, required_columns: set[str]) -> ResearchDataset:
        frame = pd.read_csv(path)
        missing = (required_columns | {"timestamp"}) - set(frame.columns)
        if missing:
            raise ValueError(f"research CSV is missing columns: {sorted(missing)}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
        if timestamps.duplicated().any():
            raise ValueError("research timestamps must be unique")
        indexed = frame.assign(timestamp=timestamps).set_index("timestamp").sort_index()
        return cls(path, indexed)

    def period(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        if self.frame.empty:
            raise ValueError("research dataset is empty")
        return self.frame.index[0], self.frame.index[-1]


class ResearchExperimentService:
    def run_no_lookahead(
        self,
        path: Path,
        signal_column: str,
        gross_edge_column: str,
        cost_column: str,
        output_directory: Path | None = None,
    ) -> dict[str, object]:
        dataset = ResearchDataset.load(
            path,
            {signal_column, gross_edge_column, cost_column},
        )
        signals = pd.to_numeric(dataset.frame[signal_column], errors="raise")
        gross_edges = pd.to_numeric(dataset.frame[gross_edge_column], errors="raise")
        costs = pd.to_numeric(dataset.frame[cost_column], errors="raise")
        result = ResearchBacktester().run_next_observation(signals, gross_edges, costs)
        payload: dict[str, object] = {
            "execution_model": "signal_at_t_evaluated_at_next_observation",
            "metrics": asdict(result.metrics),
            "trades": [asdict(trade) for trade in result.trades],
        }
        return self._finalize(
            "no_lookahead_backtest",
            dataset,
            {
                "signal_column": signal_column,
                "gross_edge_column": gross_edge_column,
                "cost_column": cost_column,
            },
            payload,
            output_directory,
        )

    def run_multi_stage(
        self,
        path: Path,
        stages: tuple[SignalStage, ...],
        gross_edge_column: str,
        cost_column: str,
        ensemble_threshold: float,
        output_directory: Path | None = None,
    ) -> dict[str, object]:
        dataset = ResearchDataset.load(
            path,
            {stage.column for stage in stages} | {gross_edge_column, cost_column},
        )
        result = MultiStageBacktester().run(
            dataset.frame,
            stages,
            gross_edge_column,
            cost_column,
            ensemble_threshold,
        )
        payload: dict[str, object] = {
            "execution_model": "multi_stage_signal_at_t_evaluated_at_next_observation",
            "ensemble_metrics": asdict(result.ensemble.metrics),
            "ensemble_trades": [asdict(trade) for trade in result.ensemble.trades],
            "stage_metrics": {
                name: asdict(stage_result.metrics) for name, stage_result in result.stages.items()
            },
            "stage_weights": result.stage_weights,
            "ensemble_threshold": result.activation_threshold,
        }
        return self._finalize(
            "multi_stage_backtest",
            dataset,
            {
                "stages": [asdict(stage) for stage in stages],
                "gross_edge_column": gross_edge_column,
                "cost_column": cost_column,
                "ensemble_threshold": ensemble_threshold,
            },
            payload,
            output_directory,
        )

    def run_walk_forward(
        self,
        path: Path,
        signal_column: str,
        gross_edge_column: str,
        cost_column: str,
        config: WalkForwardConfig,
        output_directory: Path | None = None,
    ) -> dict[str, object]:
        dataset = ResearchDataset.load(
            path,
            {signal_column, gross_edge_column, cost_column},
        )
        result = WalkForwardValidator().run(
            dataset.frame,
            config,
            signal_column,
            gross_edge_column,
            cost_column,
        )
        payload: dict[str, object] = {
            "selection": "threshold_selected_on_train_only",
            "completed_folds": result.completed_folds,
            "aggregate_test_metrics": asdict(result.aggregate_test_metrics),
            "folds": [asdict(fold) for fold in result.folds],
        }
        return self._finalize(
            "walk_forward_validation",
            dataset,
            {
                "signal_column": signal_column,
                "gross_edge_column": gross_edge_column,
                "cost_column": cost_column,
                "train_observations": config.train_observations,
                "validation_observations": config.validation_observations,
                "test_observations": config.test_observations,
                "step_observations": config.step_observations,
                "thresholds": list(config.thresholds),
                "minimum_train_observations": config.minimum_train_observations,
            },
            payload,
            output_directory,
        )

    def _finalize(
        self,
        experiment_type: str,
        dataset: ResearchDataset,
        parameters: dict[str, object],
        payload: dict[str, object],
        output_directory: Path | None,
    ) -> dict[str, object]:
        start, end = dataset.period()
        manifest = create_experiment_manifest(
            experiment_type,
            dataset.source_path,
            start.to_pydatetime(),
            end.to_pydatetime(),
            parameters,
        )
        response: dict[str, object] = {"experiment": manifest.to_dict(), "results": payload}
        if output_directory is not None:
            response["report_path"] = str(
                ExperimentReportWriter(output_directory).write(payload, manifest)
            )
        return response


def build_signal_stages(
    columns: list[str],
    weights: list[float] | None = None,
    thresholds: list[float] | None = None,
) -> tuple[SignalStage, ...]:
    if not columns:
        raise ValueError("at least one stage column is required")
    resolved_weights = weights or [1.0] * len(columns)
    resolved_thresholds = thresholds or [0.0] * len(columns)
    if len(resolved_weights) != len(columns) or len(resolved_thresholds) != len(columns):
        raise ValueError("stage weights and thresholds must match stage columns")
    return tuple(
        SignalStage(column, column, weight, threshold)
        for column, weight, threshold in zip(
            columns,
            resolved_weights,
            resolved_thresholds,
            strict=True,
        )
    )
