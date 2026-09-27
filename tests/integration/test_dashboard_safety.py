from pathlib import Path


def test_dashboard_contains_research_safety_banner() -> None:
    source = Path("src/market_relationship_discovery/dashboard/app.py").read_text(encoding="utf-8")

    assert "DEMO / RESEARCH MODE" in source
    assert "NO LIVE TRADING" in source
    assert "order_send" not in source
    assert "Discrepancy Explorer" in source
    assert "Broker Comparison" in source
    assert "settings.mt5.password" not in source
    assert "settings.mt5.login" not in source


def test_research_package_has_no_order_execution_path() -> None:
    package = Path("src/market_relationship_discovery")
    offenders = [
        str(path)
        for path in package.rglob("*.py")
        if "order_send(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_roadmap_keeps_optional_execution_out_of_scope() -> None:
    roadmap = Path("docs/roadmap/ROADMAP.md").read_text(encoding="utf-8")

    assert "Not implemented and explicitly out of scope" in roadmap
    assert "separately authorized" in roadmap
