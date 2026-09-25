from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Self


def _require_utc(timestamp: datetime) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    if timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ValueError("timestamp must use UTC")


@dataclass(frozen=True, slots=True)
class Quote:
    timestamp: datetime
    broker: str
    symbol: str
    bid: float
    ask: float
    source: str
    volume: int | float | None = None
    source_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        _require_utc(self.timestamp)
        if self.source_timestamp is None:
            object.__setattr__(self, "source_timestamp", self.timestamp)
        else:
            _require_utc(self.source_timestamp)
        if not self.broker or not self.symbol or not self.source:
            raise ValueError("broker, symbol, and source are required")
        if not all(isfinite(value) for value in (self.bid, self.ask)):
            raise ValueError("prices must be finite")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("prices must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @classmethod
    def create(
        cls,
        timestamp: datetime,
        broker: str,
        symbol: str,
        bid: float,
        ask: float,
        source: str,
        volume: int | float | None = None,
        timestamp_offset_minutes: int = 0,
    ) -> Self:
        source_timestamp = timestamp.astimezone(UTC)
        normalized = source_timestamp + timedelta(minutes=timestamp_offset_minutes)
        return cls(
            normalized,
            broker,
            symbol,
            bid,
            ask,
            source,
            volume,
            source_timestamp,
        )


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: datetime
    broker: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str
    source_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        _require_utc(self.timestamp)
        if self.source_timestamp is None:
            object.__setattr__(self, "source_timestamp", self.timestamp)
        else:
            _require_utc(self.source_timestamp)
        values = (self.open, self.high, self.low, self.close)
        if not all(isfinite(value) for value in values):
            raise ValueError("bar prices must be finite")
        if (
            min(values) <= 0
            or self.high < max(self.open, self.close)
            or self.low > min(self.open, self.close)
        ):
            raise ValueError("invalid OHLC values")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")

    @classmethod
    def create(
        cls,
        timestamp: datetime,
        broker: str,
        symbol: str,
        timeframe: str,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        source: str,
        timestamp_offset_minutes: int = 0,
    ) -> Self:
        source_timestamp = timestamp.astimezone(UTC)
        normalized = source_timestamp + timedelta(minutes=timestamp_offset_minutes)
        return cls(
            normalized,
            broker,
            symbol,
            timeframe,
            open,
            high,
            low,
            close,
            volume,
            source,
            source_timestamp,
        )
