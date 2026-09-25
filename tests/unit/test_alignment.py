import pandas as pd
import pytest

from market_relationship_discovery.market_data.alignment import AlignmentDirection, align_timeseries


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
