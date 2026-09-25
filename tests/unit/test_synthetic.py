from datetime import UTC, datetime

import pytest

from market_relationship_discovery.domain.errors import InvalidFormulaError
from market_relationship_discovery.domain.market import Quote
from market_relationship_discovery.synthetic.engine import DiscrepancyKind, SyntheticPriceEngine


def quote(symbol: str, bid: float, ask: float) -> Quote:
    return Quote.create(
        datetime(2026, 9, 25, tzinfo=UTC),
        "DemoBroker",
        symbol,
        bid,
        ask,
        "test",
    )


def test_gold_eur_known_relationship() -> None:
    quotes = {
        "XAUUSD": quote("XAUUSD", 2999.0, 3001.0),
        "EURUSD": quote("EURUSD", 1.1999, 1.2001),
        "XAUEUR": quote("XAUEUR", 2500.0, 2500.0),
    }

    result = SyntheticPriceEngine().evaluate("XAUUSD / EURUSD", quotes, "XAUEUR")

    assert result.theoretical_price == pytest.approx(2500.0)
    assert result.discrepancy is not None
    assert result.discrepancy.kind is DiscrepancyKind.NONE


def test_bid_ask_discrepancy_is_executable_only_when_prices_cross() -> None:
    quotes = {
        "EURUSD": quote("EURUSD", 1.2000, 1.2002),
        "GBPUSD": quote("GBPUSD", 1.5000, 1.5002),
        "EURGBP": quote("EURGBP", 0.8002, 0.8003),
    }

    result = SyntheticPriceEngine().evaluate("EURUSD / GBPUSD", quotes, "EURGBP")

    assert result.discrepancy is not None
    assert result.discrepancy.kind is DiscrepancyKind.EXECUTABLE
    assert result.discrepancy.buy_target_sell_synthetic > 0


def test_mid_only_difference_is_theoretical() -> None:
    quotes = {
        "A": quote("A", 100.0, 100.0),
        "B": quote("B", 2.0, 2.0),
        "TARGET": quote("TARGET", 49.9, 52.1),
    }

    result = SyntheticPriceEngine().evaluate("A / B", quotes, "TARGET")

    assert result.discrepancy is not None
    assert result.discrepancy.kind is DiscrepancyKind.THEORETICAL
    assert result.discrepancy.buy_target_sell_synthetic == pytest.approx(-0.1)


def test_missing_quote_is_reported() -> None:
    with pytest.raises(InvalidFormulaError):
        SyntheticPriceEngine().evaluate("A / B", {"A": quote("A", 1.0, 1.0)}, "TARGET")
