from enum import StrEnum
from typing import Literal

import pandas as pd


class AlignmentDirection(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    NEAREST = "nearest"


def align_timeseries(
    left: pd.DataFrame,
    right: pd.DataFrame,
    max_delay_ms: int,
    direction: AlignmentDirection = AlignmentDirection.BACKWARD,
) -> pd.DataFrame:
    if "timestamp" not in left or "timestamp" not in right:
        raise ValueError("both frames require a timestamp column")
    if max_delay_ms < 0:
        raise ValueError("max_delay_ms cannot be negative")
    left_index = left.assign(timestamp=pd.to_datetime(left["timestamp"], utc=True)).sort_values(
        "timestamp"
    )
    right_index = right.assign(
        _right_timestamp=pd.to_datetime(right["timestamp"], utc=True),
        timestamp=pd.to_datetime(right["timestamp"], utc=True),
    ).sort_values("timestamp")
    merge_direction: Literal["backward", "forward", "nearest"]
    if direction is AlignmentDirection.BACKWARD:
        merge_direction = "backward"
    elif direction is AlignmentDirection.FORWARD:
        merge_direction = "forward"
    else:
        merge_direction = "nearest"
    result = pd.merge_asof(
        left_index,
        right_index,
        on="timestamp",
        suffixes=("_left", "_right"),
        direction=merge_direction,
        tolerance=pd.Timedelta(milliseconds=max_delay_ms),
    )
    result["alignment_delay_ms"] = (
        result["timestamp"] - result["_right_timestamp"]
    ).dt.total_seconds() * 1000.0
    return result.drop(columns=["_right_timestamp"])
