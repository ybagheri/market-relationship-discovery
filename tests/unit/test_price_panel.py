from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import DataQualityError
from market_relationship_discovery.market_data.panel import load_price_panel


def test_load_price_panel_accepts_wide_csv(tmp_path: Path) -> None:
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:01:00Z"],
            "EURUSD": [1.1, 1.2],
            "GBPUSD": [1.3, 1.4],
        }
    ).to_csv(path, index=False)

    result = load_price_panel(path)

    assert list(result.columns) == ["EURUSD", "GBPUSD"]
    assert str(result.index.tz) == "UTC"
    assert result.index.is_monotonic_increasing


def test_load_price_panel_pivots_long_format(tmp_path: Path) -> None:
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": [
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:01:00Z",
                "2026-09-25T00:01:00Z",
            ],
            "symbol": ["EURUSD", "GBPUSD", "EURUSD", "GBPUSD"],
            "close": [1.1, 1.3, 1.2, 1.4],
        }
    ).to_csv(path, index=False)

    result = load_price_panel(path)

    assert result.shape == (2, 2)
    assert result.loc[result.index[0], "EURUSD"] == 1.1


def test_load_price_panel_rejects_duplicate_wide_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z"],
            "EURUSD": [1.1, 1.2],
        }
    ).to_csv(path, index=False)

    with pytest.raises(DataQualityError, match="unique"):
        load_price_panel(path)
