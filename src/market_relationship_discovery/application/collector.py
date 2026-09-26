from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import pandas as pd

from market_relationship_discovery import __version__
from market_relationship_discovery.domain.dataset import (
    CollectionBatch,
    DatasetManifest,
    DataType,
    StoredDataset,
)
from market_relationship_discovery.domain.errors import DataQualityError, MT5ConnectionError
from market_relationship_discovery.domain.market import Bar, Quote
from market_relationship_discovery.infrastructure.mt5.adapter import AccountSnapshot
from market_relationship_discovery.infrastructure.storage.quotes import ParquetQuoteRepository
from market_relationship_discovery.validation.quality import MarketDataValidator


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    broker_profile: str
    symbols: tuple[str, ...]
    data_type: DataType
    timeframe: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int | None = None
    source_utc_offset_minutes: int = 0
    tick_lookback_hours: int = 168


class HistoricalDataSource(Protocol):
    def account_info(self) -> AccountSnapshot: ...

    def ticks(self, symbol: str, start: datetime, end: datetime) -> list[Quote]: ...

    def recent_ticks(self, symbol: str, start: datetime, count: int) -> list[Quote]: ...

    def bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Bar]: ...

    def recent_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]: ...


class HistoricalCollector:
    def __init__(
        self,
        source: HistoricalDataSource,
        repository: ParquetQuoteRepository,
        validator: MarketDataValidator | None = None,
    ) -> None:
        self._source = source
        self._repository = repository
        self._validator = validator or MarketDataValidator()

    def collect(self, request: CollectionRequest) -> CollectionBatch:
        self._validate_request(request)
        datasets = tuple(
            self._collect_symbol(request, symbol) for symbol in dict.fromkeys(request.symbols)
        )
        return CollectionBatch(request.broker_profile, datasets)

    def _validate_request(self, request: CollectionRequest) -> None:
        if not request.symbols:
            raise ValueError("at least one symbol is required")
        if request.limit is not None and request.limit < 1:
            raise ValueError("limit must be positive")
        if request.data_type is DataType.BAR and not request.timeframe:
            raise ValueError("timeframe is required for bar collection")
        if request.limit is None and (request.start is None or request.end is None):
            raise ValueError("start and end are required when limit is not provided")
        if request.start is not None:
            if request.start.tzinfo is None or request.start.utcoffset() is None:
                raise ValueError("start must be timezone-aware")
            request.start.astimezone(UTC)
        if request.end is not None:
            if request.end.tzinfo is None or request.end.utcoffset() is None:
                raise ValueError("end must be timezone-aware")
            request.end.astimezone(UTC)
        if request.start is not None and request.end is not None and request.start >= request.end:
            raise ValueError("start must be before end")

    def _collect_symbol(self, request: CollectionRequest, symbol: str) -> StoredDataset:
        if request.data_type is DataType.TICK:
            quotes = self._collect_ticks(request, symbol)
            if not quotes:
                raise MT5ConnectionError(f"MT5 returned no tick data for {symbol}")
            frame = self._quotes_to_frame(quotes)
            report = self._validator.validate(frame)
        else:
            if request.timeframe is None:
                raise ValueError("timeframe is required")
            bars = self._collect_bars(request, symbol, request.timeframe)
            if not bars:
                raise MT5ConnectionError(f"MT5 returned no bar data for {symbol}")
            frame = self._bars_to_frame(bars)
            report = self._validator.validate_bars(frame)
        tick_duplicates_only = (
            request.data_type is DataType.TICK
            and report.duplicate_timestamps > 0
            and report.invalid_quotes == 0
            and report.invalid_bars == 0
            and report.missing_values == 0
            and not report.issues
        )
        if not report.is_valid and not tick_duplicates_only:
            raise DataQualityError(f"Collection quality check failed: {report}")
        if frame.empty:
            raise MT5ConnectionError(f"MT5 returned no {request.data_type.value} data for {symbol}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True)
        start = timestamps.min().to_pydatetime()
        end = timestamps.max().to_pydatetime()
        dataset_id = f"DATA-{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
        file_name = f"{dataset_id}.parquet"
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            created_at=datetime.now(UTC),
            broker_profile=request.broker_profile,
            broker_server=self._source.account_info().server,
            symbol=symbol,
            data_type=request.data_type,
            timeframe=request.timeframe,
            start=start,
            end=end,
            rows=len(frame),
            source="MetaTrader5",
            software_version=__version__,
            file_name=file_name,
            parameters={
                "requested_start": request.start.isoformat() if request.start else None,
                "requested_end": request.end.isoformat() if request.end else None,
                "limit": request.limit,
                "source_utc_offset_minutes": request.source_utc_offset_minutes,
            },
            quality={
                "duplicate_timestamps": report.duplicate_timestamps,
                "invalid_quotes": report.invalid_quotes,
                "invalid_bars": report.invalid_bars,
                "missing_values": report.missing_values,
                "issues": report.issues,
            },
        )
        return self._repository.write(frame, manifest)

    def _collect_ticks(self, request: CollectionRequest, symbol: str) -> list[Quote]:
        if request.limit is not None:
            # The search floor has to sit behind the most recent tick. Anchoring
            # it at the current time yields nothing whenever the market is
            # closed, which is the normal case outside trading hours.
            earliest = datetime.now(UTC) - timedelta(hours=request.tick_lookback_hours)
            return self._source.recent_ticks(symbol, earliest, request.limit)
        if request.start is None or request.end is None:
            raise ValueError("tick range is incomplete")
        return self._source.ticks(symbol, request.start, request.end)

    def _collect_bars(
        self,
        request: CollectionRequest,
        symbol: str,
        timeframe: str,
    ) -> list[Bar]:
        if request.limit is not None:
            return self._source.recent_bars(symbol, timeframe, request.limit)
        if request.start is None or request.end is None:
            raise ValueError("bar range is incomplete")
        return self._source.bars(symbol, timeframe, request.start, request.end)

    @staticmethod
    def _quotes_to_frame(rows: list[Quote]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": row.timestamp,
                    "source_timestamp": row.source_timestamp,
                    "broker": row.broker,
                    "symbol": row.symbol,
                    "bid": row.bid,
                    "ask": row.ask,
                    "mid": row.mid,
                    "spread": row.spread,
                    "volume": row.volume,
                    "source": row.source,
                }
                for row in rows
            ]
        )

    @staticmethod
    def _bars_to_frame(rows: list[Bar]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": row.timestamp,
                    "source_timestamp": row.source_timestamp,
                    "broker": row.broker,
                    "symbol": row.symbol,
                    "timeframe": row.timeframe,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                    "source": row.source,
                }
                for row in rows
            ]
        )
