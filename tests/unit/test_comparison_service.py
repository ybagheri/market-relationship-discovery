import json
from pathlib import Path

import pandas as pd

from market_relationship_discovery.application.comparison import CrossBrokerExperimentService
from market_relationship_discovery.market_data.cross_broker import ComparisonKind


def test_comparison_service_records_both_sources_and_report(tmp_path: Path) -> None:
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    timestamps_a = pd.date_range("2026-09-25", periods=3, freq="min", tz="UTC")
    timestamps_b = timestamps_a + pd.Timedelta(milliseconds=20)
    pd.DataFrame(
        {
            "timestamp": timestamps_a,
            "symbol": "EURUSD",
            "bid": [1.1000, 1.1001, 1.1002],
            "ask": [1.1002, 1.1003, 1.1004],
        }
    ).to_csv(source_a, index=False)
    pd.DataFrame(
        {
            "timestamp": timestamps_b,
            "symbol": "EURUSD",
            "bid": [1.1006, 1.1006, 1.1006],
            "ask": [1.1008, 1.1008, 1.1008],
        }
    ).to_csv(source_b, index=False)

    result = CrossBrokerExperimentService().run(
        source_a,
        source_b,
        "BrokerA",
        "BrokerB",
        "EURUSD",
        ComparisonKind.TICK,
        100,
        0.0001,
        tmp_path / "reports",
    )

    assert result["experiment"]["source_file_name"] == "a.csv"
    assert result["experiment"]["related_sources"][0]["file_name"] == "b.csv"
    assert result["experiment"]["related_sources"][0]["sha256"]
    assert result["results"]["summary"]["crossable_observations"] == 3
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert report["manifest"]["related_sources"][0]["file_name"] == "b.csv"
