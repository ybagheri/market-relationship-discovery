from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from market_relationship_discovery.relationships.catalog import RelationshipDefinition
from market_relationship_discovery.research.service import HistoricalRelationshipResearcher


def frame(symbol: str, values: list[float]) -> pd.DataFrame:
    start = datetime(2026, 9, 25, tzinfo=UTC)
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=index) for index in range(len(values))],
            "symbol": symbol,
            "close": values,
        }
    )


def test_historical_research_evaluates_synthetic_formula() -> None:
    eurusd = [1.2 + index / 10000 for index in range(20)]
    gbpusd = [1.5 + index / 20000 for index in range(20)]
    eurgbp = [eurusd[index] / gbpusd[index] for index in range(20)]
    relationship = RelationshipDefinition("EURGBP_TEST", "EURGBP", "EURUSD / GBPUSD")
    researcher = HistoricalRelationshipResearcher(100, 5, 10, rolling_beta_window=5)

    result = researcher.run(
        relationship,
        {
            "EURUSD": frame("EURUSD", eurusd),
            "GBPUSD": frame("GBPUSD", gbpusd),
            "EURGBP": frame("EURGBP", eurgbp),
        },
    )

    assert result.observations == 20
    assert result.mean_discrepancy == pytest.approx(0.0, abs=1e-12)
    assert result.executable_discrepancy_claimed is False
    assert result.classification == "requires_further_validation"
    assert result.beta_stability["valid_windows"] > 0
    assert result.cointegration_stationarity["status"] == "available"


def test_historical_research_requires_complete_alignment() -> None:
    relationship = RelationshipDefinition("EURGBP_TEST", "EURGBP", "EURUSD / GBPUSD")
    researcher = HistoricalRelationshipResearcher(100, 5, 3)

    with pytest.raises(ValueError, match="missing symbol series"):
        researcher.run(
            relationship,
            {
                "EURUSD": frame("EURUSD", [1.2, 1.3]),
                "EURGBP": frame("EURGBP", [0.8, 0.9]),
            },
        )
