from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a price panel without letting the CSV reader reinterpret a symbol.

    Instrument codes are frequently numeric with leading zeros — exchange codes
    such as `000300` and `600000` are the common case — and `read_csv` infers an
    integer column from them, turning `000300` into `300`. The panel then
    reports a symbol that no broker publishes, and the original name can never be
    joined back to it. Reading the CSV twice is avoided: the header is read with
    `dtype=str` so no column is ever inferred as a number in the first place, and
    the price columns are converted explicitly below, where a genuinely
    non-numeric price is reported as the data error it is.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=True)


def load_price_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else _read_csv(path)
    if "timestamp" not in frame:
        raise DataQualityError("price panel requires a timestamp column")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    if timestamps.isna().any():
        raise DataQualityError("price panel timestamps must be valid")
    if "symbol" in frame.columns or "close" in frame.columns:
        required = {"symbol", "close"}
        missing = required - set(frame.columns)
        if missing:
            raise DataQualityError(f"long price panel is missing columns: {sorted(missing)}")
        # The code is the row's identity, so it is read as written rather than
        # as a number the reader can round-trip lossily.
        working = frame.assign(timestamp=timestamps, symbol=frame["symbol"].astype(str))
        if working.duplicated(["timestamp", "symbol"]).any():
            raise DataQualityError("long price panel contains duplicate timestamp-symbol rows")
        result = working.pivot(index="timestamp", columns="symbol", values="close")
    else:
        if timestamps.duplicated().any():
            raise DataQualityError("wide price panel timestamps must be unique")
        result = frame.drop(columns=["timestamp"]).copy()
        result.index = pd.DatetimeIndex(timestamps, name="timestamp")
        # A wide panel names its symbols in the header, which the CSV reader
        # leaves untouched; only the values are converted.
    result = result.sort_index().sort_index(axis=1)
    if result.empty or not len(result.columns):
        raise DataQualityError("price panel must contain at least one symbol")
    result = result.apply(pd.to_numeric, errors="raise")
    if (result.dropna(how="all").stack() <= 0).any():
        raise DataQualityError("price panel values must be positive")
    return result
