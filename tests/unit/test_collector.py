from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from market_relationship_discovery.application.collector import (
    CollectionRequest,
    HistoricalCollector,
)
from market_relationship_discovery.domain.dataset import DataType
from market_relationship_discovery.domain.market import Bar, Quote
from market_relationship_discovery.infrastructure.mt5.adapter import AccountSnapshot
from market_relationship_discovery.infrastructure.storage.quotes import ParquetQuoteRepository


class FakeHistoricalSource:
    def account_info(self) -> AccountSnapshot:
        return AccountSnapshot("DEMO", "DemoServer", "USD", 100)

    def ticks(self, symbol: str, start: datetime, end: datetime) -> list[Quote]:
        return self.recent_ticks(symbol, start, 3)

    def recent_ticks(self, symbol: str, start: datetime, count: int) -> list[Quote]:
        return [
            Quote(
                timestamp=start - timedelta(seconds=count - index),
                broker="DemoServer",
                symbol=symbol,
                bid=1.0 + index / 10000,
                ask=1.0001 + index / 10000,
                source="fake",
                volume=index,
            )
            for index in range(count)
        ]

    def bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Bar]:
        return self.recent_bars(symbol, timeframe, 3)

    def recent_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        start = datetime(2026, 9, 25, tzinfo=UTC)
        return [
            Bar(
                timestamp=start + timedelta(minutes=index),
                broker="DemoServer",
                symbol=symbol,
                timeframe=timeframe,
                open=1.0,
                high=1.1,
                low=0.9,
                close=1.0 + index / 1000,
                volume=100 + index,
                source="fake",
            )
            for index in range(count)
        ]


def test_collector_writes_parquet_and_reproducible_manifest(tmp_path: Path) -> None:
    repository = ParquetQuoteRepository(tmp_path / "raw")
    collector = HistoricalCollector(FakeHistoricalSource(), repository)

    batch = collector.collect(
        CollectionRequest(
            broker_profile="broker_a",
            symbols=("EURUSD",),
            data_type=DataType.BAR,
            timeframe="M1",
            limit=3,
        )
    )

    assert batch.rows == 3
    stored = batch.datasets[0]
    frame = repository.read(stored.data_path)
    manifest = repository.read_manifest(stored.manifest_path)
    assert len(frame) == 3
    assert manifest["broker_profile"] == "broker_a"
    assert manifest["software_version"] == "0.7.0"
    assert manifest["quality"]["invalid_bars"] == 0
    assert manifest["file_name"] == stored.data_path.name
    assert str(tmp_path) not in str(manifest)


def test_collector_rejects_naive_time_range(tmp_path: Path) -> None:
    collector = HistoricalCollector(
        FakeHistoricalSource(),
        ParquetQuoteRepository(tmp_path / "raw"),
    )
    request = CollectionRequest(
        broker_profile="broker_a",
        symbols=("EURUSD",),
        data_type=DataType.TICK,
        start=datetime(2026, 9, 25),
        end=datetime(2026, 9, 26),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        collector.collect(request)
