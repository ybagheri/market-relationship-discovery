from dataclasses import dataclass, field

import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    rows: int
    duplicate_timestamps: int
    invalid_quotes: int
    missing_values: int
    invalid_bars: int = 0
    issues: dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not any(
            (
                self.duplicate_timestamps,
                self.invalid_quotes,
                self.invalid_bars,
                self.missing_values,
                self.issues,
            )
        )


class MarketDataValidator:
    def validate(self, frame: pd.DataFrame) -> DataQualityReport:
        required = {"timestamp", "broker", "symbol", "bid", "ask"}
        missing_columns = required - set(frame.columns)
        if missing_columns:
            raise DataQualityError(f"missing columns: {sorted(missing_columns)}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        duplicate_count = int(timestamps.duplicated().sum())
        invalid_quotes = int(
            (
                (frame["bid"] <= 0)
                | (frame["ask"] <= 0)
                | (frame["bid"] > frame["ask"])
                | ~frame["bid"].map(lambda value: value == value)
                | ~frame["ask"].map(lambda value: value == value)
            ).sum()
        )
        missing_values = int(
            frame[["timestamp", "broker", "symbol", "bid", "ask"]].isna().sum().sum()
        )
        issues: dict[str, int] = {}
        if timestamps.isna().any():
            issues["invalid_timestamp"] = int(timestamps.isna().sum())
        return DataQualityReport(
            rows=len(frame),
            duplicate_timestamps=duplicate_count,
            invalid_quotes=invalid_quotes,
            missing_values=missing_values,
            issues=issues,
        )

    def validate_bars(self, frame: pd.DataFrame) -> DataQualityReport:
        required = {"timestamp", "broker", "symbol", "open", "high", "low", "close", "volume"}
        missing_columns = required - set(frame.columns)
        if missing_columns:
            raise DataQualityError(f"missing columns: {sorted(missing_columns)}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        prices = frame[["open", "high", "low", "close"]]
        invalid_bars = int(
            (
                (prices <= 0).any(axis=1)
                | (frame["high"] < frame[["open", "close"]].max(axis=1))
                | (frame["low"] > frame[["open", "close"]].min(axis=1))
                | (frame["volume"] < 0)
            ).sum()
        )
        missing_values = int(frame[list(required)].isna().sum().sum())
        issues: dict[str, int] = {}
        if timestamps.isna().any():
            issues["invalid_timestamp"] = int(timestamps.isna().sum())
        return DataQualityReport(
            rows=len(frame),
            duplicate_timestamps=int(timestamps.duplicated().sum()),
            invalid_quotes=0,
            missing_values=missing_values,
            invalid_bars=invalid_bars,
            issues=issues,
        )
