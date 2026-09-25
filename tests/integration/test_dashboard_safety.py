from pathlib import Path


def test_dashboard_contains_research_safety_banner() -> None:
    source = Path("src/market_relationship_discovery/dashboard/app.py").read_text(encoding="utf-8")

    assert "DEMO / RESEARCH MODE" in source
    assert "NO LIVE TRADING" in source
    assert "order_send" not in source
