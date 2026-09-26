"""Tests for cross-symbol panel coverage reporting.

The motivating failure was a panel collected in one request whose symbols covered
entirely different calendar ranges. It surfaced as ``prices must be finite
positive values`` from a statistics routine, which told the reader nothing about
the misalignment that caused it.
"""

from __future__ import annotations

import pandas as pd
import pytest

from market_relationship_discovery.domain.errors import DataQualityError
from market_relationship_discovery.validation.coverage import PanelCoverageAnalyzer


def panel_from(values: dict[str, list[float | None]], periods: int | None = None) -> pd.DataFrame:
    if periods is None:
        periods = max((len(series) for series in values.values()), default=0)
    index = pd.date_range("2026-09-25", periods=periods, freq="h", tz="UTC")
    return pd.DataFrame(values, index=index)


def test_a_fully_aligned_panel_reports_the_whole_window() -> None:
    panel = panel_from({"EURUSD": [1.1] * 10, "GBPUSD": [1.3] * 10, "EURGBP": [0.8] * 10})

    report = PanelCoverageAnalyzer().analyze(panel)

    assert report.union_rows == 10
    assert report.fully_overlapping_rows == 10
    assert report.is_usable is True
    assert report.issues == ()
    window = report.best_shared_window
    assert window is not None
    assert window.rows == 10
    assert window.symbols == ("EURGBP", "EURUSD", "GBPUSD")


def test_a_three_symbol_panel_is_not_rejected_by_a_two_symbol_threshold() -> None:
    """A per-row count of three must satisfy a threshold of two.

    Coercing the count to a boolean first collapses three to ``True``, which is
    one and therefore fails the threshold.
    """
    panel = panel_from({"A": [1.0] * 10, "B": [2.0] * 10, "C": [3.0] * 10})

    report = PanelCoverageAnalyzer().analyze(panel, minimum_symbols=2)

    assert report.best_shared_window is not None
    assert len(report.best_shared_window.symbols) == 3


def test_symbols_ending_early_are_reported_rather_than_hidden() -> None:
    panel = panel_from(
        {
            "EARLY": [1.0] * 4 + [None] * 6,
            "CONTINUES": [2.0] * 10,
        }
    )

    report = PanelCoverageAnalyzer().analyze(panel)

    assert report.fully_overlapping_rows == 4
    assert any("ending before" in issue for issue in report.issues)
    early = report.coverage_for("EARLY")
    assert early is not None
    assert early.observations == 4
    assert early.coverage_fraction == pytest.approx(0.4)


def test_a_panel_with_no_shared_timestamp_is_reported_as_unusable() -> None:
    panel = panel_from({"A": [1.0] * 5 + [None] * 5, "B": [None] * 5 + [2.0] * 5})

    report = PanelCoverageAnalyzer().analyze(panel)

    assert report.is_usable is False
    assert report.fully_overlapping_rows == 0
    assert set(report.no_overlap_symbols) == {"A", "B"}


def test_the_largest_comparable_window_is_chosen_over_a_barely_overlapping_pair() -> None:
    """Column order must not decide which symbols are compared.

    An arbitrary pair can be instruments that never trade at the same time,
    while a genuinely comparable pair exists elsewhere in the panel.
    """
    panel = panel_from(
        {
            "STALE": [None] * 6 + [1.0] * 4,
            "WIDE_A": [1.0] * 10,
            "WIDE_B": [2.0] * 10,
            "WIDE_C": [3.0] * 10,
        }
    )

    report = PanelCoverageAnalyzer().analyze(panel, minimum_symbols=2)
    window = report.best_shared_window

    assert window is not None
    assert set(window.symbols) == {"WIDE_A", "WIDE_B", "WIDE_C"}
    assert window.rows == 10


def test_a_symbol_missing_every_bar_is_reported_with_zero_coverage() -> None:
    panel = panel_from({"A": [1.0] * 6, "B": [2.0] * 6, "EMPTY": [None] * 6})

    report = PanelCoverageAnalyzer().analyze(panel)
    empty = report.coverage_for("EMPTY")

    assert empty is not None
    assert empty.observations == 0
    assert empty.span is None
    assert empty.coverage_fraction == pytest.approx(0.0)


def test_largest_gap_counts_consecutive_absent_bars() -> None:
    panel = panel_from({"A": [1.0] * 3 + [None] * 4 + [1.0] * 3})

    report = PanelCoverageAnalyzer().analyze(panel)
    coverage = report.coverage_for("A")

    assert coverage is not None
    assert coverage.largest_gap == 4


def test_require_usable_raises_an_actionable_error_for_a_misaligned_panel() -> None:
    panel = panel_from(
        {
            "A": [1.0] * 5 + [None] * 5,
            "B": [None] * 5 + [2.0] * 5,
        }
    )

    with pytest.raises(DataQualityError) as error:
        PanelCoverageAnalyzer().require_usable(panel)

    message = str(error.value)
    assert "no usable shared window" in message
    assert "different calendar ranges" in message


def test_require_usable_raises_when_the_shared_window_is_too_short() -> None:
    panel = panel_from({"A": [1.0] * 5, "B": [2.0] * 5}, periods=5)

    with pytest.raises(DataQualityError, match="too short"):
        PanelCoverageAnalyzer().require_usable(panel, minimum_observations=30)


def test_require_usable_returns_the_report_for_a_usable_panel() -> None:
    panel = panel_from({"A": [1.0] * 10, "B": [2.0] * 10})

    report = PanelCoverageAnalyzer().require_usable(panel, minimum_observations=5)

    assert report.is_usable is True
    assert report.best_shared_window is not None


def test_report_is_serializable() -> None:
    panel = panel_from({"A": [1.0] * 6, "B": [2.0] * 6, "C": [None] * 6})

    payload = PanelCoverageAnalyzer().analyze(panel).to_dict()

    assert payload["union_rows"] == 6
    assert payload["symbols"] == ["A", "B", "C"]
    assert len(payload["coverage"]) == 3
    assert "best_shared_window" in payload
    assert "issues" in payload


def test_an_empty_panel_is_rejected() -> None:
    with pytest.raises(DataQualityError):
        PanelCoverageAnalyzer().analyze(pd.DataFrame())


def test_a_non_datetime_index_is_rejected_for_coverage_analysis() -> None:
    panel = pd.DataFrame({"A": [1.0, 2.0], "B": [2.0, 3.0]}, index=[0, 1])

    with pytest.raises(DataQualityError, match="datetime index"):
        PanelCoverageAnalyzer().analyze(panel)


def test_minimum_symbols_below_two_is_rejected() -> None:
    panel = panel_from({"A": [1.0] * 4, "B": [2.0] * 4})

    with pytest.raises(ValueError, match="minimum_symbols"):
        PanelCoverageAnalyzer().analyze(panel, minimum_symbols=1)
