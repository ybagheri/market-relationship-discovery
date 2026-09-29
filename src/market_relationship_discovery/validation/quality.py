from __future__ import annotations

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


def _coerce_prices(frame: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, int]:
    """Return numeric price columns and the count that could not be read.

    A price column arriving as text is a data problem, not a programming error,
    so it is reported through the same channel as any other unusable value rather
    than raising a bare `TypeError` from a string comparison. A CSV written by a
    tool that quotes numbers, or a column holding one stray non-numeric cell,
    previously took the whole collection down with a traceback instead of a
    reason.
    """
    numeric = pd.DataFrame(index=frame.index)
    unreadable = 0
    for column in columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        # A value that was present but unreadable is worse than a missing one,
        # so the two are counted separately in the report.
        present = frame[column].notna()
        unreadable += int((present & converted.isna()).sum())
        numeric[column] = converted
    return numeric, unreadable


def _duplicate_timestamps(frame: pd.DataFrame, timestamps: pd.Series) -> int:
    """Count duplicate timestamps *within* one symbol of one broker.

    Two symbols quoting the same instant is the normal case for a multi-symbol
    bar collection, and two brokers quoting one instant is the whole basis of a
    cross-broker comparison. Counting across the whole frame therefore reported
    every such file invalid, which is a correct observation about the data
    presented as a defect in it. A duplicate is a repeated timestamp for the
    *same* symbol from the *same* broker, which is the thing that corrupts a
    series; the broker is part of the key because a file may legitimately hold
    both feeds.
    """
    keys: list[pd.Series] = [timestamps]
    for column in ("broker", "symbol"):
        if column in frame.columns:
            keys.append(frame[column].astype(str))
    return int(pd.concat(keys, axis=1).duplicated().sum())


class MarketDataValidator:
    def validate(self, frame: pd.DataFrame) -> DataQualityReport:
        required = {"timestamp", "broker", "symbol", "bid", "ask"}
        missing_columns = required - set(frame.columns)
        if missing_columns:
            raise DataQualityError(f"missing columns: {sorted(missing_columns)}")
        timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        duplicate_count = _duplicate_timestamps(frame, timestamps)
        prices, unreadable_prices = _coerce_prices(frame, ["bid", "ask"])
        invalid_quotes = int(
            ((prices["bid"] <= 0) | (prices["ask"] <= 0) | (prices["bid"] > prices["ask"])).sum()
        )
        missing_values = int(
            frame[["timestamp", "broker", "symbol", "bid", "ask"]].isna().sum().sum()
        )
        issues: dict[str, int] = {}
        if timestamps.isna().any():
            issues["invalid_timestamp"] = int(timestamps.isna().sum())
        if unreadable_prices:
            issues["unreadable_price"] = unreadable_prices
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
        price_columns = ["open", "high", "low", "close"]
        prices, unreadable_prices = _coerce_prices(frame, [*price_columns, "volume"])
        invalid_bars = int(
            (
                (prices[price_columns] <= 0).any(axis=1)
                | (prices["high"] < prices[["open", "close"]].max(axis=1))
                | (prices["low"] > prices[["open", "close"]].min(axis=1))
                | (prices["volume"] < 0)
            ).sum()
        )
        missing_values = int(frame[list(required)].isna().sum().sum())
        issues: dict[str, int] = {}
        if timestamps.isna().any():
            issues["invalid_timestamp"] = int(timestamps.isna().sum())
        if unreadable_prices:
            issues["unreadable_price"] = unreadable_prices
        return DataQualityReport(
            rows=len(frame),
            duplicate_timestamps=_duplicate_timestamps(frame, timestamps),
            invalid_quotes=0,
            missing_values=missing_values,
            invalid_bars=invalid_bars,
            issues=issues,
        )
