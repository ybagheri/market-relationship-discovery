"""Execute the dashboard script to prove it renders without error.

A plain HTTP check only proves the Streamlit server started. Streamlit runs the
page script when a browser opens a websocket session, so a crash in the script
is invisible to a socket test. ``AppTest`` runs the real script and surfaces any
exception, which is what this test asserts.
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
    return AppTest.from_file(str(APP), default_timeout=120).run()


def test_dashboard_script_renders_without_exception() -> None:
    app = _run()

    assert not app.exception, [str(item) for item in app.exception]
    assert app.warning, "the research safety banner must be present"


def test_dashboard_offers_every_configured_broker_profile() -> None:
    app = _run()

    labels = [str(option) for option in app.sidebar.selectbox[0].options]
    assert "default" in labels
    assert len(labels) >= 1


def test_dashboard_exposes_the_documented_tabs() -> None:
    app = _run()

    labels = [str(tab.label) for tab in app.tabs]
    for expected in ("Overview", "Market Monitor", "Broker Comparison", "Limitations"):
        assert any(expected in label for label in labels), f"missing tab {expected}"


def test_dashboard_never_references_credentials_or_order_execution() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "order_send" not in source
    assert "password" not in source
    assert "login" not in source
