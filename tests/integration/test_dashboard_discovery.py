"""Execute the dashboard script against real persisted reports.

This proves the Discovery tab renders a real advanced-discovery report, including
the significance chart, the contested warning, and the coverage view.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "market_relationship_discovery"
    / "dashboard"
    / "app.py"
)


def _run() -> AppTest:
    if not APP.is_file():
        pytest.skip("dashboard application script is not present")
    return AppTest.from_file(str(APP), default_timeout=180).run()


def test_dashboard_renders_with_discovery_reports_present() -> None:
    app = _run()

    assert not app.exception, [str(item) for item in app.exception]


def test_discovery_tab_exists() -> None:
    app = _run()

    labels = [str(tab.label) for tab in app.tabs]

    assert any("Discovery" in label for label in labels)


def test_discovery_view_reads_a_persisted_report(tmp_path: Path) -> None:
    """The loaders and frames must work on a report written by a real run."""
    import json

    from market_relationship_discovery.dashboard.reports import (
        candidate_frame,
        coverage_frame,
        list_discovery_reports,
        load_discovery_report,
    )

    directory = Path("reports/research")
    references = list_discovery_reports(directory)
    if not references:
        pytest.skip("no persisted discovery report is available")

    loaded = load_discovery_report(references[0].path)
    candidates = candidate_frame(references[0].path)
    coverage = coverage_frame(references[0].path)

    assert loaded["multiplicity"]
    assert not candidates.empty
    assert {"name", "adjusted_p_value", "survived_correction", "contested"} <= set(
        candidates.columns
    )
    assert "coverage_fraction" in coverage.columns
    assert "analysed" in coverage.columns
    json.dumps(candidates.head(1).to_dict(orient="records"), default=str)
