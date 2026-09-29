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


def test_a_leading_zero_symbol_code_survives_a_long_panel(tmp_path: Path) -> None:
    """Instrument codes are numeric with leading zeros, and must stay that way.

    `read_csv` inferred an integer column from `000300`, so the panel reported a
    symbol called `300`. No broker publishes that name, so the column could never
    be joined back to a broker label and the panel silently described a different
    instrument. Exchange codes like `000300` and `600000` are the common case,
    not an edge case.
    """
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": [
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:00:00Z",
            ],
            "symbol": ["000300", "600000"],
            "close": [3000.0, 1800.0],
        }
    ).to_csv(path, index=False)

    result = load_price_panel(path)

    assert list(result.columns) == ["000300", "600000"]


def test_a_leading_zero_column_name_survives_a_wide_panel(tmp_path: Path) -> None:
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:01:00Z"],
            "000300": [3000.0, 3001.0],
            "EURUSD": [1.1, 1.2],
        }
    ).to_csv(path, index=False)

    result = load_price_panel(path)

    assert list(result.columns) == ["000300", "EURUSD"]


def test_reading_symbols_as_text_does_not_leave_prices_as_strings(
    tmp_path: Path,
) -> None:
    """The price columns are still numeric, and a gap is still missing.

    Reading the CSV as text protects the symbol codes, but it must not leave the
    values unconverted or turn a gap into a parse failure.
    """
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": [
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:00:00Z",
                "2026-09-25T00:01:00Z",
            ],
            "symbol": ["000300", "600000", "000300"],
            "close": [3000.0, 1800.0, None],
        }
    ).to_csv(path, index=False)

    result = load_price_panel(path)

    assert result["000300"].dtype.kind == "f"
    assert result.loc[result.index[0], "000300"] == 3000.0
    assert pd.isna(result.loc[result.index[1], "000300"])


def test_a_non_numeric_price_is_still_reported_as_a_data_error(tmp_path: Path) -> None:
    path = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z"],
            "EURUSD": ["not-a-price"],
        }
    ).to_csv(path, index=False)

    with pytest.raises((ValueError, TypeError)):
        load_price_panel(path)
