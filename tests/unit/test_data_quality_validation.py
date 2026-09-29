"""Quality checks must describe the data, not condemn a valid file.

Two defects, both visible on a legitimate cross-broker collection.

Duplicate counting ran across the whole frame, so two symbols quoting the
same instant — the normal case for a cross-broker file and for a multi-symbol
bar collection — was reported as a duplicate timestamp. A correct observation
about the data was presented as a defect in it, and the collector raised a
quality failure for a file that was fine.

A price column arriving as text raised a bare `TypeError` from a string
comparison instead of `DataQualityError`, taking the whole collection down
with a traceback rather than a reason.
"""

from __future__ import annotations

import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import DataQualityError
from market_relationship_discovery.validation.quality import MarketDataValidator


def tick_frame(**overrides: object) -> pd.DataFrame:
    values: dict[str, object] = {
        "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:00:01Z"],
        "broker": ["A", "A"],
        "symbol": ["EURUSD", "EURUSD"],
        "bid": [1.1, 1.2],
        "ask": [1.2, 1.3],
    }
    values.update(overrides)
    return pd.DataFrame(values)


def bar_frame(**overrides: object) -> pd.DataFrame:
    values: dict[str, object] = {
        "timestamp": ["2026-09-25T00:00:00Z", "2026-09-25T00:00:01Z"],
        "broker": ["A", "A"],
        "symbol": ["EURUSD", "EURUSD"],
        "open": [1.1, 1.2],
        "high": [1.2, 1.3],
        "low": [1.0, 1.1],
        "close": [1.15, 1.25],
        "volume": [10.0, 12.0],
    }
    values.update(overrides)
    return pd.DataFrame(values)


def test_two_symbols_quoting_the_same_instant_are_not_duplicates() -> None:
    """A cross-broker file holds many symbols per instant by construction.

    Counting duplicates across the whole frame made every such file invalid, so
    a correct observation was presented as a defect in the data.
    """
    frame = pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z"] * 2 + ["2026-09-25T00:00:01Z"] * 2,
            "broker": ["A"] * 4,
            "symbol": ["EURUSD", "GBPUSD"] * 2,
            "bid": [1.1, 1.3, 1.2, 1.4],
            "ask": [1.2, 1.4, 1.3, 1.5],
        }
    )

    report = MarketDataValidator().validate(frame)

    assert report.duplicate_timestamps == 0
    assert report.is_valid is True


def test_two_symbols_sharing_an_instant_is_valid_for_bars_too() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": ["2026-09-25T00:00:00Z"] * 3,
            "broker": ["A"] * 3,
            "symbol": ["EURUSD", "GBPUSD", "USDJPY"],
            "open": [1.1, 1.3, 1.5],
            "high": [1.2, 1.4, 1.6],
            "low": [1.0, 1.2, 1.4],
            "close": [1.15, 1.35, 1.55],
            "volume": [10.0, 11.0, 12.0],
        }
    )

    report = MarketDataValidator().validate_bars(frame)

    assert report.duplicate_timestamps == 0
    assert report.is_valid is True


def test_a_repeated_timestamp_for_the_same_symbol_is_still_a_duplicate() -> None:
    """The fix must not excuse the duplicate that actually corrupts a series."""
    report = MarketDataValidator().validate(
        tick_frame(bid=[1.1, 1.1], ask=[1.2, 1.2], timestamp=["2026-09-25T00:00:00Z"] * 2)
    )

    assert report.duplicate_timestamps == 1
    assert report.is_valid is False


def test_the_same_timestamp_from_two_brokers_is_not_a_duplicate() -> None:
    """Two brokers quoting one instant is the whole basis of a comparison."""
    report = MarketDataValidator().validate(
        tick_frame(
            timestamp=["2026-09-25T00:00:00Z"] * 2,
            broker=["Alpari", "AMarkets"],
            symbol=["EURUSD", "EURUSD"],
        )
    )

    assert report.duplicate_timestamps == 0
    assert report.is_valid is True


def test_one_broker_quoting_the_same_instant_twice_is_a_duplicate() -> None:
    report = MarketDataValidator().validate(
        tick_frame(
            timestamp=["2026-09-25T00:00:00Z"] * 2,
            broker=["Alpari", "Alpari"],
            symbol=["EURUSD", "EURUSD"],
        )
    )

    assert report.duplicate_timestamps == 1
    assert report.is_valid is False


def test_a_text_price_column_is_read_rather_than_crashing() -> None:
    """A quoted number is a data problem, not a programming error.

    It previously raised a bare `TypeError` from a string comparison, taking the
    collection down with a traceback instead of a reason.
    """
    report = MarketDataValidator().validate(tick_frame(bid=["1.1", "1.2"], ask=["1.2", "1.3"]))

    assert report.is_valid is True
    assert report.invalid_quotes == 0
    assert report.issues == {}


def test_a_single_unreadable_price_is_reported_as_such() -> None:
    report = MarketDataValidator().validate(tick_frame(ask=[1.2, "not-a-price"]))

    assert report.issues == {"unreadable_price": 1}
    assert report.is_valid is False


def test_a_text_bar_column_is_reported_rather_than_crashing() -> None:
    report = MarketDataValidator().validate_bars(bar_frame(close=["1.15", "bad"]))

    assert report.issues == {"unreadable_price": 1}
    assert report.is_valid is False


def test_a_missing_price_is_still_counted_as_missing_not_unreadable() -> None:
    """The two are different: one is absent, the other is present and unparseable."""
    report = MarketDataValidator().validate(tick_frame(bid=[1.1, None]))

    assert report.missing_values == 1
    assert report.issues == {}


def test_a_genuinely_duplicate_bar_still_fails() -> None:
    report = MarketDataValidator().validate_bars(bar_frame(timestamp=["2026-09-25T00:00:00Z"] * 2))

    assert report.duplicate_timestamps == 1
    assert report.is_valid is False


def test_an_inverted_bar_is_still_rejected() -> None:
    frame = bar_frame()
    frame.loc[0, "high"] = 1.0

    report = MarketDataValidator().validate_bars(frame)

    assert report.invalid_bars == 1
    assert report.is_valid is False


def test_a_crossed_quote_is_still_rejected() -> None:
    report = MarketDataValidator().validate(tick_frame(bid=[1.3, 1.2], ask=[1.2, 1.3]))

    assert report.invalid_quotes == 1
    assert report.is_valid is False


def test_missing_columns_are_still_a_data_error() -> None:
    with pytest.raises(DataQualityError, match="missing columns"):
        MarketDataValidator().validate(pd.DataFrame({"timestamp": []}))


def test_an_invalid_timestamp_is_still_reported() -> None:
    report = MarketDataValidator().validate(tick_frame(timestamp=["not-a-time", "x"]))

    assert report.issues["invalid_timestamp"] == 2
    assert report.is_valid is False
