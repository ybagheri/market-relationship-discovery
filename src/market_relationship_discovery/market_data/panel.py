from __future__ import annotations

from pathlib import Path

import pandas as pd

from market_relationship_discovery.domain.errors import DataQualityError


def load_price_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
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
        working = frame.assign(timestamp=timestamps, symbol=frame["symbol"].astype(str))
        if working.duplicated(["timestamp", "symbol"]).any():
            raise DataQualityError("long price panel contains duplicate timestamp-symbol rows")
        result = working.pivot(index="timestamp", columns="symbol", values="close")
    else:
        if timestamps.duplicated().any():
            raise DataQualityError("wide price panel timestamps must be unique")
        result = frame.drop(columns=["timestamp"]).copy()
        result.index = pd.DatetimeIndex(timestamps, name="timestamp")
    result = result.sort_index().sort_index(axis=1)
    if result.empty or not len(result.columns):
        raise DataQualityError("price panel must contain at least one symbol")
    result = result.apply(pd.to_numeric, errors="raise")
    if (result.dropna(how="all").stack() <= 0).any():
        raise DataQualityError("price panel values must be positive")
    return result
