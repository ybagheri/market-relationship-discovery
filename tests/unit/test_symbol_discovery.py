from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from market_relationship_discovery.market_data.symbols import (
    MatchReason,
    SymbolDescriptor,
    SymbolSearchService,
    SymbolTradeMode,
    describe_matches,
)


def descriptor(
    name: str,
    description: str = "",
    trade_mode: int | None = 4,
    digits: int = 2,
    spread: int | None = 0,
    visible: bool = False,
) -> SymbolDescriptor:
    return SymbolDescriptor(
        name=name,
        description=description,
        path="",
        currency_base="USD",
        currency_profit="USD",
        digits=digits,
        point=0.01,
        spread=spread,
        trade_mode=trade_mode,
        visible=visible,
    )


@dataclass
class FakeCatalog:
    descriptors: list[SymbolDescriptor]

    def symbol_details(self, visible_only: bool = False) -> list[SymbolDescriptor]:
        if visible_only:
            return [item for item in self.descriptors if item.visible]
        return list(self.descriptors)


ALPARI_LIKE = [
    descriptor("XAUUSD", "Gold (Spot)", spread=19, visible=True),
    descriptor("XAUEUR", "Gold vs. Euro"),
    descriptor("XAGUSD", "Silver (Spot)", spread=29, digits=3),
    descriptor("EURUSD", "Euro vs US Dollar", digits=5, spread=18),
    descriptor("EURGBP", "Euro vs Great Britain Pound", digits=5),
    descriptor("EURJPY", "Euro vs Japanese Yen", digits=3),
    descriptor("DOW CFD", "陶氏 CFD", trade_mode=0),
    descriptor("EURONET CFD", "EURONET 全球 CFD", trade_mode=0),
]


def test_gold_query_matches_broker_specific_names() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    results = service.search("gold")

    names = [result.name for result in results]
    assert "XAUUSD" in names
    assert "XAUEUR" in names


def test_silver_query_matches_broker_specific_names() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    results = service.search("silver")

    assert [result.name for result in results] == ["XAGUSD"]
    assert results[0].reason is MatchReason.ALIAS
    assert results[0].canonical_symbol == "XAGUSD"


def test_dollar_query_matches_descriptions_not_names() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    results = service.search("dollar")

    assert "EURUSD" in [result.name for result in results]
    assert results[0].reason is MatchReason.DESCRIPTION


def test_exact_name_match_outranks_looser_matches() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    results = service.search("xauusd")

    assert len(results) == 1
    assert results[0].reason is MatchReason.EXACT_NAME


def test_disabled_broker_symbols_are_excluded_by_default() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    tradable = service.search("c fd")
    everything = service.search("c fd", tradable_only=False)

    assert [result.name for result in tradable] == []
    assert "DOW CFD" in [result.name for result in everything]


def test_unknown_trade_mode_is_never_treated_as_tradable() -> None:
    service = SymbolSearchService(FakeCatalog([descriptor("MYSTERY", "Mystery", trade_mode=None)]))

    assert service.search("mystery") == []

    result = service.search("mystery", tradable_only=False)[0]

    assert result.is_tradable is False
    assert result.descriptor.trade_mode_name == "unknown"


def test_trade_mode_parsing_covers_official_mt5_constants() -> None:
    assert SymbolTradeMode.parse(0) is SymbolTradeMode.DISABLED
    assert SymbolTradeMode.parse(1) is SymbolTradeMode.LONG_ONLY
    assert SymbolTradeMode.parse(2) is SymbolTradeMode.SHORT_ONLY
    assert SymbolTradeMode.parse(3) is SymbolTradeMode.CLOSE_ONLY
    assert SymbolTradeMode.parse(4) is SymbolTradeMode.FULL
    assert SymbolTradeMode.parse(99) is None
    assert SymbolTradeMode.parse(None) is None


def test_visible_only_search_is_restricted_to_watch_window() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    all_results = service.search("gold")
    visible_results = service.search("gold", visible_only=True)

    assert {result.name for result in all_results} == {"XAUUSD", "XAUEUR"}
    assert [result.name for result in visible_results] == ["XAUUSD"]


def test_empty_query_lists_the_whole_tradable_catalog_by_default() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    default_results = service.search(None)
    everything = service.search(None, tradable_only=False)

    assert len(default_results) == 6
    assert len(everything) == len(ALPARI_LIKE)
    assert all(result.is_tradable for result in default_results)


def test_descriptions_with_non_ascii_text_do_not_break_rendering() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    rendered = describe_matches(service.search("c fd", tradable_only=False))

    assert "陶氏 CFD" in rendered
    assert "DOW CFD" in rendered


def test_find_canonical_locates_broker_implementation() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    found = service.find_canonical("XAUUSD")

    assert found is not None
    assert found.name == "XAUUSD"
    assert found.canonical_symbol == "XAUUSD"


def test_find_canonical_returns_none_when_absent() -> None:
    service = SymbolSearchService(FakeCatalog(ALPARI_LIKE))

    assert service.find_canonical("USDJPY") is None


def test_cli_symbols_json_payload_is_machine_readable(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from market_relationship_discovery import cli

    class FakeAdapter:
        def __init__(self, settings: object) -> None:
            self._settings = settings

        def __enter__(self) -> FakeAdapter:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def symbol_details(self, visible_only: bool = False) -> list[SymbolDescriptor]:
            return list(ALPARI_LIKE)

    monkeypatch.setattr(cli, "MT5Adapter", FakeAdapter)

    exit_code = cli.main(["symbols", "--search", "gold", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["catalog_size"] == len(ALPARI_LIKE)
    assert payload["tradable_count"] == 6
    assert {item["name"] for item in payload["symbols"]} == {"XAUUSD", "XAUEUR"}
