from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.application.commands import run_no_lookahead_backtest
from market_relationship_discovery.cli import build_parser


def test_backtest_command_uses_next_observation(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {
            "timestamp": [
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:01:00Z",
                "2026-09-25T00:02:00Z",
            ],
            "signal": [1, 0, 0],
            "gross_edge": [100.0, 0.01, 0.02],
            "cost": [0.0, 0.001, 0.002],
        }
    )
    path = tmp_path / "signals.csv"
    source.to_csv(path, index=False)

    result = run_no_lookahead_backtest(
        path,
        "signal",
        "gross_edge",
        "cost",
        tmp_path / "reports",
    )

    assert result["results"]["execution_model"] == "signal_at_t_evaluated_at_next_observation"
    assert result["results"]["metrics"]["gross_edge"] == 0.01
    assert result["experiment"]["source_sha256"]
    assert Path(result["report_path"]).is_file()


def test_backtest_command_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    source = pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z"],
            "signal": [1, 0],
            "gross_edge": [0.01, 0.02],
            "cost": [0.0, 0.0],
        }
    )
    path = tmp_path / "duplicate.csv"
    source.to_csv(path, index=False)

    with pytest.raises(ValueError, match="unique"):
        run_no_lookahead_backtest(path, "signal", "gross_edge", "cost")


def test_discover_accepts_repeated_symbol_options() -> None:
    arguments = build_parser().parse_args(["discover", "--symbol", "EURUSD", "--symbol", "GBPUSD"])

    assert arguments.symbol == [["EURUSD"], ["GBPUSD"]]


def test_walk_forward_and_multi_stage_commands_are_available() -> None:
    parser = build_parser()

    walk = parser.parse_args(["walk-forward", "signals.csv"])
    multi = parser.parse_args(
        [
            "multi-backtest",
            "signals.csv",
            "--stage-column",
            "momentum",
            "--stage-column",
            "confirmation",
        ]
    )

    assert walk.command == "walk-forward"
    assert multi.stage_column == ["momentum", "confirmation"]


def test_robustness_command_exposes_reproducibility_parameters() -> None:
    arguments = build_parser().parse_args(
        [
            "robustness",
            "signals.csv",
            "--simulations",
            "500",
            "--seed",
            "9",
            "--block-size",
            "4",
            "--scenario",
            "combined_stress",
        ]
    )

    assert arguments.simulations == 500
    assert arguments.seed == 9
    assert arguments.block_size == 4
    assert arguments.scenario == ["combined_stress"]


def test_compare_brokers_command_exposes_alignment_and_cost_controls() -> None:
    arguments = build_parser().parse_args(
        [
            "compare-brokers",
            "a.parquet",
            "b.parquet",
            "--broker-a",
            "A",
            "--broker-b",
            "B",
            "--symbol",
            "EURUSD",
            "--kind",
            "tick",
            "--max-delay-ms",
            "50",
            "--additional-cost",
            "0.0002",
        ]
    )

    assert arguments.max_delay_ms == 50
    assert arguments.additional_cost == 0.0002
    assert arguments.kind == "tick"


def test_contract_commands_are_available() -> None:
    parser = build_parser()
    compare = parser.parse_args(
        [
            "compare-brokers",
            "a.csv",
            "b.csv",
            "--broker-a",
            "A",
            "--broker-b",
            "B",
            "--symbol",
            "EURUSD",
            "--contract-a",
            "a.json",
            "--contract-b",
            "b.json",
        ]
    )
    specs = parser.parse_args(["symbol-specs", "--symbol", "EURUSD"])

    assert compare.contract_a == Path("a.json")
    assert compare.contract_b == Path("b.json")
    assert compare.sync_mode == "anchor_a"
    assert compare.tick_aggregation == "last"
    assert specs.symbol == ["EURUSD"]


def test_collect_command_exposes_parallel_worker_controls() -> None:
    arguments = build_parser().parse_args(
        [
            "collect",
            "--broker-profile",
            "A",
            "--broker-profile",
            "B",
            "--symbol",
            "EURUSD",
            "--parallel",
            "--max-workers",
            "2",
        ]
    )

    assert arguments.parallel is True
    assert arguments.max_workers == 2
    assert arguments.broker_profile == ["A", "B"]
