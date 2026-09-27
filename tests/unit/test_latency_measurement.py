import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.costs import measurement
from market_relationship_discovery.costs.measurement import (
    LatencyStatistic,
    load_measured_latency,
)
from market_relationship_discovery.domain.errors import DataQualityError


def _csv(path: Path) -> Path:
    pd.DataFrame(
        {
            "round_trip_ms": [80.0, 100.0, 120.0],
            "symbol": ["EURUSD", "EURUSD", "GBPUSD"],
            "broker": ["A", "B", "A"],
        }
    ).to_csv(path, index=False)
    return path


def test_measured_log_replaces_the_assumed_baseline(tmp_path: Path) -> None:
    baseline = load_measured_latency(_csv(tmp_path / "latency.csv"), LatencyStatistic.MEAN)

    assert baseline.round_trip_ms == 100.0
    assert baseline.per_leg(2) == 50.0
    assert baseline.sample_count == 3
    assert baseline.to_dict()["source_kind"] == "measured"


def test_json_and_csv_logs_produce_the_same_baseline(tmp_path: Path) -> None:
    csv = load_measured_latency(_csv(tmp_path / "latency.csv"), LatencyStatistic.MEDIAN)
    json_path = tmp_path / "latency.json"
    json_path.write_text(
        json.dumps(
            {
                "samples": [
                    {"round_trip_ms": 80.0, "symbol": "EURUSD", "broker": "A"},
                    {"round_trip_ms": 100.0, "symbol": "EURUSD", "broker": "B"},
                    {"round_trip_ms": 120.0, "symbol": "GBPUSD", "broker": "A"},
                ]
            }
        ),
        encoding="utf-8",
    )

    from_json = load_measured_latency(json_path, LatencyStatistic.MEDIAN)

    assert from_json.round_trip_ms == csv.round_trip_ms


def test_pre_aggregated_json_summary_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"round_trip_ms": 87.4, "symbol": "EURUSD"}), encoding="utf-8")

    baseline = load_measured_latency(path, LatencyStatistic.MAXIMUM)

    assert baseline.round_trip_ms == 87.4
    assert baseline.sample_count == 1


def test_filters_are_applied_and_empty_results_are_reported(tmp_path: Path) -> None:
    path = _csv(tmp_path / "latency.csv")

    baseline = load_measured_latency(path, LatencyStatistic.MEDIAN, symbol="EURUSD")

    assert baseline.sample_count == 2
    with pytest.raises(DataQualityError, match="no observations"):
        load_measured_latency(path, symbol="XAUUSD")


def test_zero_or_negative_round_trip_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "latency.csv"
    path.write_text("round_trip_ms\n0\n", encoding="utf-8")

    with pytest.raises(DataQualityError, match="must be positive"):
        load_measured_latency(path)


def test_measurement_module_never_opens_a_terminal() -> None:
    source = inspect.getsource(measurement)

    assert "MT5Adapter" not in source
    assert "order_send" not in source
