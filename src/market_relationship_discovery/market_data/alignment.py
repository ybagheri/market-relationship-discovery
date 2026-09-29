from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import pandas as pd


class AlignmentDirection(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    NEAREST = "nearest"


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    """Aligned observations together with what alignment could not match.

    Unmatched rows used to survive as rows full of `NaN` with an undefined delay,
    so a caller could neither trust the row count nor tell a missing observation
    from a matched one. A row that is not an observation is dropped, and its
    count is reported, which is what the cross-broker layer already did.
    """

    frame: pd.DataFrame
    matched: int
    unmatched_left: int
    unmatched_right: int

    def to_dict(self) -> dict[str, int]:
        return {
            "matched_observations": self.matched,
            "unmatched_left_rows": self.unmatched_left,
            "unmatched_right_rows": self.unmatched_right,
        }


def align_timeseries(
    left: pd.DataFrame,
    right: pd.DataFrame,
    max_delay_ms: int,
    direction: AlignmentDirection = AlignmentDirection.BACKWARD,
) -> pd.DataFrame:
    """Align two time series within a tolerance.

    Kept for callers that want a frame. Prefer :func:`align` when the counts of
    dropped rows matter, because a frame of `NaN` rows is not an observation of
    anything.
    """
    return align(left, right, max_delay_ms, direction).frame


def align(
    left: pd.DataFrame,
    right: pd.DataFrame,
    max_delay_ms: int,
    direction: AlignmentDirection = AlignmentDirection.BACKWARD,
) -> AlignmentResult:
    """Join two series on time within a tolerance, reporting what did not match.

    Only matched rows are returned. A row that failed to match is not a
    measurement, and returning it with `NaN` prices and an undefined delay made
    an alignment look larger than the evidence it contained.
    """
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
    # Sign convention, stated because the two alignments in this package differ:
    # positive means the matched right observation is *older* than the left one,
    # so the right feed reached backwards to meet it, and negative means it
    # reached forwards into the left row's future. A forward match is only
    # possible under FORWARD and NEAREST, and it is the sign that tells a reader
    # an alignment consumed an observation from the future.
    #
    # `cross_broker` reports the same-named column as `right - left`, so the two
    # are opposites. They never feed one report, and no calculation branches on
    # the sign, but a reader comparing the two would otherwise read them as the
    # same quantity.
    # A delay is only defined for a matched row, and every other column arrived
    # empty for the same reason.
    matched_mask = result["_right_timestamp"].notna()
    matched_rows = int(matched_mask.sum())
    matched_right_timestamps = result.loc[matched_mask, "_right_timestamp"]
    # A right-hand row that no left row reached is also unaligned. Counting it
    # from the timestamps actually used avoids reporting a right row as matched
    # when it was only ever a candidate.
    unique_matched = int(matched_right_timestamps.nunique())
    return AlignmentResult(
        frame=result.loc[matched_mask].drop(columns=["_right_timestamp"]).reset_index(drop=True),
        matched=matched_rows,
        unmatched_left=int(len(result) - matched_rows),
        unmatched_right=int(len(right_index) - unique_matched),
    )
