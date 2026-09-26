import json
from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.application.comparison import CrossBrokerExperimentService
from market_relationship_discovery.domain.errors import DataQualityError
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


def test_broker_specific_symbol_labels_are_mapped_to_one_research_symbol(
    tmp_path: Path,
) -> None:
    """Brokers rarely name an instrument identically.

    The observed configuration has one broker publishing bitcoin as ``BITCOIN``
    and the other as ``BTCUSD``. Without per-source labels the cross-broker
    study cannot read either file, so the service must accept the broker label
    for each source while reporting a single research symbol.
    """
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    timestamps = pd.date_range("2026-09-25", periods=3, freq="min", tz="UTC")
    pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": "BITCOIN",
            "bid": [83900.0, 83901.0, 83902.0],
            "ask": [83902.0, 83903.0, 83904.0],
        }
    ).to_csv(source_a, index=False)
    pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": "BTCUSD",
            "bid": [83906.0, 83906.0, 83906.0],
            "ask": [83908.0, 83908.0, 83908.0],
        }
    ).to_csv(source_b, index=False)

    result = CrossBrokerExperimentService().run(
        source_a,
        source_b,
        "BrokerA",
        "BrokerB",
        "BTCUSD",
        ComparisonKind.TICK,
        100,
        0.0,
        symbol_a="BITCOIN",
        symbol_b="BTCUSD",
    )

    summary = result["results"]["summary"]
    assert summary["symbol"] == "BTCUSD"
    assert summary["aligned_observations"] == 3
    assert result["experiment"]["parameters"]["symbol_a"] == "BITCOIN"
    assert result["experiment"]["parameters"]["symbol_b"] == "BTCUSD"


def test_missing_broker_label_is_reported_clearly(tmp_path: Path) -> None:
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    timestamps = pd.date_range("2026-09-25", periods=2, freq="min", tz="UTC")
    for path, symbol in ((source_a, "BITCOIN"), (source_b, "BTCUSD")):
        pd.DataFrame(
            {
                "timestamp": timestamps,
                "symbol": symbol,
                "bid": [1.0, 1.0],
                "ask": [1.1, 1.1],
            }
        ).to_csv(path, index=False)

    with pytest.raises(DataQualityError, match="no rows for BTCUSD"):
        CrossBrokerExperimentService().run(
            source_a,
            source_b,
            "BrokerA",
            "BrokerB",
            "BTCUSD",
            ComparisonKind.TICK,
            100,
            0.0,
        )
