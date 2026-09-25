from pathlib import Path

import numpy as np
import pandas as pd

from market_relationship_discovery.application.advanced_research import AdvancedDiscoveryService
from market_relationship_discovery.discovery.ranker import CandidateRankingConfig


def test_advanced_discovery_writes_advanced_research_report(tmp_path: Path) -> None:
    source = tmp_path / "prices.csv"
    index = pd.date_range("2026-09-25", periods=80, freq="h", tz="UTC")
    eurusd = np.linspace(1.1, 1.2, 80)
    gbpusd = np.linspace(1.3, 1.4, 80)
    pd.DataFrame(
        {
            "timestamp": index,
            "EURUSD": eurusd,
            "GBPUSD": gbpusd,
            "EURGBP": eurusd / gbpusd,
        }
    ).to_csv(source, index=False)

    result = AdvancedDiscoveryService().run(
        source,
        minimum_observations=30,
        regime_window=5,
        max_depth=1,
        ranking_config=CandidateRankingConfig(minimum_train_rows=10),
        output_directory=tmp_path / "reports",
    )

    assert result["experiment"]["experiment_type"] == "advanced_relationship_discovery"
    assert result["experiment"]["source_sha256"]
    assert result["results"]["graph"]["max_depth"] == 1
    assert result["results"]["regimes"]
    assert result["results"]["candidates"]
    assert result["results"]["ranking"]["model"] == "numpy_ridge"
    report_path = Path(result["report_path"])
    assert report_path.is_file()
    report_text = report_path.read_text(encoding="utf-8")
    assert str(source) not in report_text
