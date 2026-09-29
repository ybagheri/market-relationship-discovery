import pandas as pd
import pytest

from market_relationship_discovery.market_data.alignment import (
    AlignmentDirection,
    align,
    align_timeseries,
)


def test_alignment_reports_delay_and_rejects_stale_data() -> None:
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T10:00:00.100Z", "2026-09-25T10:00:01.000Z"], utc=True
            ),
            "left_value": [1.0, 2.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T10:00:00.000Z", "2026-09-25T10:00:00.900Z"], utc=True
            ),
            "right_value": [10.0, 20.0],
        }
    )

    result = align_timeseries(left, right, 100, AlignmentDirection.BACKWARD)

    assert result["right_value"].tolist() == [10.0, 20.0]
    assert result["alignment_delay_ms"].tolist() == [100.0, 100.0]
    assert pd.isna(result["right_value"].iloc[0]) is False


def test_negative_tolerance_is_rejected() -> None:
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2026-09-25"], utc=True)})
    with pytest.raises(ValueError):
        align_timeseries(frame, frame, -1)


def test_an_unmatched_row_is_not_returned_as_an_observation() -> None:
    """A row full of `NaN` is not a measurement.

    Unmatched rows previously survived with undefined prices and an undefined
    delay, so the returned frame was larger than the evidence in it and a caller
    could not tell a matched row from a missing one.
    """
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T00:00:00.000Z", "2026-09-25T00:00:01.000Z"], utc=True
            ),
            "left_value": [1.0, 2.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "right_value": [10.0],
        }
    )

    result = align(left, right, 100)

    assert len(result.frame) == 1
    assert result.frame["right_value"].tolist() == [10.0]
    assert result.frame["alignment_delay_ms"].tolist() == [0.0]


def test_the_counts_say_what_alignment_could_not_match() -> None:
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-09-25T00:00:00.000Z",
                    "2026-09-25T00:00:00.200Z",
                    "2026-09-25T00:00:01.000Z",
                ],
                utc=True,
            ),
            "left_value": [1.0, 2.0, 3.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T00:00:00.100Z", "2026-09-25T00:00:05.000Z"], utc=True
            ),
            "right_value": [10.0, 20.0],
        }
    )

    counts = align(left, right, 100).to_dict()

    assert counts["matched_observations"] == 1
    assert counts["unmatched_left_rows"] == 2
    assert counts["unmatched_right_rows"] == 1


def test_a_right_row_within_tolerance_is_matched_only_once() -> None:
    """Several left rows may reach one right row; the right row is used once."""
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T00:00:00.100Z", "2026-09-25T00:00:00.150Z"], utc=True
            ),
            "left_value": [1.0, 2.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.100Z"], utc=True),
            "right_value": [10.0],
        }
    )

    counts = align(left, right, 100).to_dict()

    assert counts["matched_observations"] == 2
    assert counts["unmatched_right_rows"] == 0


def test_the_aligned_frame_carries_no_undefined_delay() -> None:
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "left_value": [1.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "right_value": [10.0],
        }
    )

    frame = align_timeseries(left, right, 100)

    assert frame["alignment_delay_ms"].notna().all()
    assert frame["right_value"].notna().all()


def test_the_frame_helper_still_returns_only_a_frame() -> None:
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "left_value": [1.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "right_value": [10.0],
        }
    )

    assert isinstance(align_timeseries(left, right, 100), pd.DataFrame)


def test_each_direction_still_selects_its_own_neighbour() -> None:
    left = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00.000Z"], utc=True),
            "left_value": [1.0],
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-09-25T00:00:00.100Z", "2026-09-25T00:00:00.200Z"], utc=True
            ),
            "right_value": [10.0, 20.0],
        }
    )

    backward = align_timeseries(left, right, 500, AlignmentDirection.BACKWARD)
    forward = align_timeseries(left, right, 500, AlignmentDirection.FORWARD)
    nearest = align_timeseries(left, right, 500, AlignmentDirection.NEAREST)

    assert backward["right_value"].tolist() == []  # nothing before the left instant
    assert forward["right_value"].tolist() == [10.0]
    assert nearest["right_value"].tolist() == [10.0]
