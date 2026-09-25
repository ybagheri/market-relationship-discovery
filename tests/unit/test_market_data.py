from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import DataQualityError, SymbolNotFoundError
from market_relationship_discovery.domain.market import Quote
from market_relationship_discovery.market_data.symbols import SymbolMapper
from market_relationship_discovery.validation.quality import MarketDataValidator


def test_symbol_mapper_uses_alias() -> None:
    match = SymbolMapper().resolve("XAUUSD", ["EURUSD", "GOLD#"])

    assert match.broker_symbol == "GOLD#"
    assert match.strategy == "alias"


def test_symbol_mapper_raises_for_unknown_symbol() -> None:
    with pytest.raises(SymbolNotFoundError):
        SymbolMapper().resolve("XAUEUR", ["EURUSD"])


def test_quality_report_detects_invalid_quotes() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z"],
            "broker": ["Demo", "Demo"],
            "symbol": ["EURUSD", "EURUSD"],
            "bid": [1.1, 1.2],
            "ask": [1.0, 1.3],
        }
    )

    report = MarketDataValidator().validate(frame)

    assert report.duplicate_timestamps == 1
    assert report.invalid_quotes == 1
    assert report.is_valid is False


def test_quality_report_requires_columns() -> None:
    with pytest.raises(DataQualityError):
        MarketDataValidator().validate(pd.DataFrame({"timestamp": []}))


def test_explicit_source_timestamp_offset_preserves_raw_time() -> None:
    source_timestamp = datetime(2026, 9, 25, 8, tzinfo=UTC)

    quote = Quote.create(
        source_timestamp,
        "Demo",
        "EURUSD",
        1.1,
        1.2,
        "test",
        timestamp_offset_minutes=-180,
    )

    assert quote.timestamp == source_timestamp - timedelta(minutes=180)
    assert quote.source_timestamp == source_timestamp
