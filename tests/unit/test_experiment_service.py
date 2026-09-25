from pathlib import Path

import pandas as pd

from market_relationship_discovery.application.experiments import (
    ResearchExperimentService,
    build_signal_stages,
)
from market_relationship_discovery.backtesting.monte_carlo import MonteCarloConfig
from market_relationship_discovery.backtesting.walk_forward import WalkForwardConfig


def test_experiment_service_runs_and_records_walk_forward(tmp_path: Path) -> None:
    index = pd.date_range("2026-09-25", periods=40, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "signal": [0.8 if value % 3 == 0 else 0.2 for value in range(40)],
            "gross_edge": [0.001 + (value % 4) / 1000 for value in range(40)],
            "cost": 0.0001,
        }
    )
    path = tmp_path / "signals.csv"
    frame.to_csv(path, index=False)
    config = WalkForwardConfig(12, 8, 8, 8, thresholds=(0.0, 0.5, 0.9))

    result = ResearchExperimentService().run_walk_forward(
        path,
        "signal",
        "gross_edge",
        "cost",
        config,
        tmp_path / "reports",
    )

    assert result["results"]["selection"] == "threshold_selected_on_train_only"
    assert result["results"]["completed_folds"] == 2
    assert result["experiment"]["experiment_type"] == "walk_forward_validation"
    assert Path(result["report_path"]).is_file()


def test_experiment_service_runs_multi_stage_ensemble(tmp_path: Path) -> None:
    index = pd.date_range("2026-09-25", periods=8, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "momentum": [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0],
            "confirmation": [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0],
            "gross_edge": 0.001,
            "cost": 0.0001,
        }
    )
    path = tmp_path / "multi.csv"
    frame.to_csv(path, index=False)

    result = ResearchExperimentService().run_multi_stage(
        path,
        build_signal_stages(["momentum", "confirmation"], [0.5, 0.5]),
        "gross_edge",
        "cost",
        0.0,
    )

    assert result["experiment"]["experiment_type"] == "multi_stage_backtest"
    assert result["results"]["stage_weights"] == {"momentum": 0.5, "confirmation": 0.5}
    assert result["results"]["ensemble_metrics"]["observations"] == 4


def test_experiment_service_runs_monte_carlo_robustness(tmp_path: Path) -> None:
    index = pd.date_range("2026-09-25", periods=20, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": index,
            "signal": 1.0,
            "gross_edge": 0.01,
            "cost": 0.001,
        }
    )
    path = tmp_path / "robustness.csv"
    frame.to_csv(path, index=False)

    result = ResearchExperimentService().run_robustness(
        path,
        "signal",
        "gross_edge",
        "cost",
        MonteCarloConfig(simulations=100, random_seed=5, block_size=2),
        ["baseline", "combined_stress"],
        output_directory=tmp_path / "reports",
    )

    assert result["experiment"]["experiment_type"] == "monte_carlo_robustness"
    assert result["results"]["trade_count"] == 19
    assert set(result["results"]["scenarios"]) == {"baseline", "combined_stress"}
    assert Path(result["report_path"]).is_file()
