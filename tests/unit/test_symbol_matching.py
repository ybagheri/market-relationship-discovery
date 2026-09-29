"""Symbol matching must reflect how well a symbol matched, not catalog order.

Two defects, both visible on the live Alpari/AMarkets demo catalogs.

Alias resolution used a bare substring test, so `XAUUSD` also matched
`XAUUSDmicro` and a search for silver returned `SILVER WHEATON CFD`, an equity
the broker happened to name with the word in it.

Result ordering ranked on which rule fired and then on the symbol name, so a
description match that merely mentioned the query outranked one that led with
it: `oil` returned `USAHO` ("US Heating Oil") above `WTI` ("WTI Crude Oil"), and
`BRN` ("Brent Crude Oil") came third. The answer depended on the broker's
alphabetical order rather than on the match.
"""

from __future__ import annotations

import pytest

from market_relationship_discovery.domain.errors import SymbolNotFoundError
from market_relationship_discovery.market_data.symbols import (
    MatchReason,
    SymbolDescriptor,
    SymbolMapper,
    SymbolSearchService,
)


class Catalog:
    def __init__(self, descriptors: list[SymbolDescriptor]) -> None:
        self._descriptors = descriptors

    def symbol_details(self, visible_only: bool = ...) -> list[SymbolDescriptor]:
        return list(self._descriptors)


def descriptor(
    name: str,
    description: str = "",
    path: str = "p",
    tradable: bool = True,
) -> SymbolDescriptor:
    return SymbolDescriptor(
        name=name,
        description=description or name,
        path=path,
        currency_base="USD",
        currency_profit="USD",
        digits=2,
        point=0.01,
        spread=10,
        trade_mode=4 if tradable else 0,
    )


def service(*descriptors: SymbolDescriptor) -> SymbolSearchService:
    return SymbolSearchService(Catalog(list(descriptors)))


def test_a_similar_prefix_is_not_the_same_instrument() -> None:
    """`XAUUSDmicro` is a different instrument and must not satisfy `XAUUSD`.

    The old substring test returned the first name the broker happened to list,
    so which instrument was chosen depended on the catalog rather than on the
    request.
    """
    available = ["XAUUSDmicro", "XAUUSD"]

    match = SymbolMapper().resolve("XAUUSD", available)

    assert match.broker_symbol == "XAUUSD"


def test_a_suffix_makes_it_a_different_instrument() -> None:
    """Only one of these is the spot instrument the research symbol means."""
    with pytest.raises(SymbolNotFoundError):
        SymbolMapper().resolve("XAUUSD", ["XAUUSDmicro"])


def test_a_separated_variant_is_still_a_match() -> None:
    """Broker separators are not a different instrument."""
    match = SymbolMapper().resolve("EURUSD", ["EUR/USD"])

    assert match.broker_symbol == "EUR/USD"


def test_an_alias_inside_a_longer_equity_name_is_not_an_alias_match() -> None:
    """A query that is a fragment of one word is not a match for that name.

    `silverwheat...` contains "silver", but the name is one token after
    normalizing, so there is no `silver` instrument here. The word-boundary
    test is what separates this from `XAUUSD`, where the name is a single token
    that *is* the query.
    """
    with pytest.raises(SymbolNotFoundError):
        SymbolMapper().resolve("SILVER", ["SILVERWHEATONCFD"])


def test_a_query_that_is_a_real_word_in_the_name_still_matches() -> None:
    """The boundary test must not reject a genuine whole-word match.

    `SILVER WHEATON CFD` really does contain the word `silver`; suppressing that
    would hide a symbol whose name genuinely contains the query.
    """
    match = SymbolMapper().resolve("SILVER", ["SILVER WHEATON CFD"])

    assert match.broker_symbol == "SILVER WHEATON CFD"


def test_a_leading_description_match_outranks_one_that_mentions_it_in_passing() -> None:
    """`oil` should lead with `WTI Crude Oil`, not `US Heating Oil`.

    Both matched on description, so the old ordering fell through to the symbol
    name and returned `USAHO` first.
    """
    results = service(
        descriptor("USAHO", "US Heating Oil CFD (5,000 gallons), cash (USD)"),
        descriptor("WTI", "WTI Crude Oil"),
        descriptor("BRN", "Brent Crude Oil"),
    ).search("oil")

    assert results[0].name == "WTI"
    assert results[0].reason is MatchReason.DESCRIPTION


def test_the_order_does_not_depend_on_the_catalog_order() -> None:
    """The same catalog in a different order must give the same answer."""
    wti = descriptor("WTI", "WTI Crude Oil")
    heating = descriptor("USAHO", "US Heating Oil CFD")

    forward = service(wti, heating).search("oil")
    reversed_ = service(heating, wti).search("oil")

    assert [item.name for item in forward] == [item.name for item in reversed_]
    assert forward[0].name == "WTI"


def test_an_exact_name_still_wins_over_everything() -> None:
    results = service(
        descriptor("XAUUSDmicro"),
        descriptor("XAUUSD"),
        descriptor("XAUEUR"),
    ).search("XAUUSD")

    assert results[0].name == "XAUUSD"
    assert results[0].reason is MatchReason.EXACT_NAME


def test_a_query_matching_nothing_returns_nothing_rather_than_a_guess() -> None:
    """A query absent from every name and description returns nothing.

    The old substring test matched any name containing the query characters, so
    a query could return an unrelated instrument instead of nothing.
    """
    results = service(
        descriptor("LAS VEGAS SANDS CFD"),
        descriptor("SILVER WHEATON CFD"),
    ).search("bitcoin")

    assert results == []


def test_the_shortest_extra_text_breaks_a_tie_between_equal_matches() -> None:
    """Two identical-quality matches are ordered by the shorter symbol name."""
    results = service(
        descriptor("BRENTOIL"),
        descriptor("OIL"),
    ).search("OIL")

    assert results[0].name == "OIL"
