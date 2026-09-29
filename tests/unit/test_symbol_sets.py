"""A study's symbol list belongs in configuration, not on the command line.

Two brokers rarely publish an instrument the same way, so the research question
is written once with canonical names and each profile maps them. Repeating the
list on every command line risks two runs of the "same" study describing
different instruments, and a naming difference surfaces as a collection failure
half way through rather than as a report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from market_relationship_discovery.application.commands import resolve_symbol_set
from market_relationship_discovery.cli import build_parser
from market_relationship_discovery.config.settings import (
    MT5Settings,
    Settings,
    SymbolSetSettings,
)
from market_relationship_discovery.domain.errors import MarketRelationshipError


def settings_with_sets(sets: SymbolSetSettings) -> Settings:
    return Settings(symbol_sets=sets)


def test_a_named_set_resolves() -> None:
    resolved = SymbolSetSettings(sets={"metals": ["XAUUSD", "XAGUSD"]})

    assert resolved.resolve("metals") == ("metals", ["XAUUSD", "XAGUSD"])


def test_the_default_set_is_named_default() -> None:
    resolved = SymbolSetSettings(default=["EURUSD"])

    assert resolved.resolve("default") == ("default", ["EURUSD"])


def test_an_unknown_set_names_the_ones_that_exist() -> None:
    resolved = SymbolSetSettings(sets={"metals": ["XAUUSD"]})

    with pytest.raises(MarketRelationshipError) as caught:
        resolved.resolve("crypto")

    assert "metals" in str(caught.value)


def test_selecting_nothing_names_the_remedy() -> None:
    """A silent fallback would run a study on symbols nobody asked for."""
    with pytest.raises(MarketRelationshipError) as caught:
        SymbolSetSettings(default=["EURUSD"]).resolve(None)

    message = str(caught.value)
    assert "--symbol-set" in message


def test_an_empty_default_set_is_refused_rather_than_collecting_nothing() -> None:
    resolved = SymbolSetSettings(sets={"metals": ["XAUUSD"]})

    with pytest.raises(MarketRelationshipError, match="default symbol set is empty"):
        resolved.resolve("default")


def test_an_empty_named_set_is_rejected_at_configuration_time() -> None:
    with pytest.raises(ValueError, match="empty"):
        SymbolSetSettings(sets={"metals": []})


def test_defining_the_default_set_twice_is_rejected() -> None:
    """Two sources for one name would make it ambiguous which applies."""
    with pytest.raises(ValueError, match="not as an entry"):
        SymbolSetSettings(default=["EURUSD"], sets={"default": ["XAUUSD"]})


def test_the_default_and_a_named_default_cannot_agree_silently() -> None:
    with pytest.raises(ValueError):
        SymbolSetSettings(default=["EURUSD"], sets={"default": ["EURUSD"]})


def _write_env(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_a_set_is_read_from_the_environment(tmp_path: Path, monkeypatch) -> None:
    _write_env(
        tmp_path / ".env",
        'SYMBOL_SETS__SETS={"metals":["XAUUSD","XAGUSD"]}\n',
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYMBOL_SETS__SETS", raising=False)
    monkeypatch.delenv("SYMBOL_SETS__DEFAULT", raising=False)

    from market_relationship_discovery.config.settings import Settings as Reloaded

    assert Reloaded().symbol_sets.resolve("metals")[1] == ["XAUUSD", "XAGUSD"]


def test_the_default_set_is_read_from_the_environment(tmp_path: Path, monkeypatch) -> None:
    _write_env(tmp_path / ".env", 'SYMBOL_SETS__DEFAULT=["EURUSD","XAUUSD"]\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SYMBOL_SETS__SETS", raising=False)
    monkeypatch.delenv("SYMBOL_SETS__DEFAULT", raising=False)

    from market_relationship_discovery.config.settings import Settings as Reloaded

    assert Reloaded().symbol_sets.resolve("default")[1] == ["EURUSD", "XAUUSD"]


@pytest.mark.parametrize("command", ["collect", "discover", "symbol-specs", "resolve-symbols"])
def test_every_symbol_command_accepts_a_set(command: str) -> None:
    parser = build_parser()
    arguments = parser.parse_args([command, "--symbol-set", "metals"])

    assert arguments.symbol_set == "metals"


def test_collect_no_longer_requires_an_inline_symbol() -> None:
    """The set replaces the repeated list, so the flag cannot stay mandatory."""
    arguments = build_parser().parse_args(["collect", "--symbol-set", "metals"])

    assert arguments.symbol is None


def test_symbol_specs_no_longer_requires_an_inline_symbol() -> None:
    arguments = build_parser().parse_args(["symbol-specs", "--symbol-set", "metals"])

    assert arguments.symbol is None


def test_explicit_symbols_and_a_set_are_unioned_without_duplicates(
    monkeypatch,
) -> None:
    """A set carries the study; `--symbol` adds a one-off without repeating it."""
    from market_relationship_discovery.cli import _requested_symbols

    settings = settings_with_sets(SymbolSetSettings(sets={"metals": ["XAUUSD", "XAGUSD"]}))
    monkeypatch.setattr("market_relationship_discovery.cli.get_settings", lambda: settings)
    arguments = build_parser().parse_args(
        ["collect", "--symbol-set", "metals", "--symbol", "XAUUSD", "--symbol", "EURUSD"]
    )

    assert _requested_symbols(arguments, settings) == ["XAUUSD", "EURUSD", "XAGUSD"]


def test_requesting_no_symbols_at_all_is_refused() -> None:
    from market_relationship_discovery.cli import _requested_symbols

    settings = settings_with_sets(SymbolSetSettings())
    arguments = build_parser().parse_args(["collect"])

    with pytest.raises(MarketRelationshipError) as caught:
        _requested_symbols(arguments, settings)

    assert "--symbol-set" in str(caught.value)


def test_repeated_discover_symbols_are_flattened_in_order(monkeypatch) -> None:
    """`--symbol A B --symbol C` must yield A, B, C rather than nesting."""
    from market_relationship_discovery.cli import _requested_symbols

    settings = settings_with_sets(SymbolSetSettings())
    arguments = build_parser().parse_args(
        ["discover", "--symbol", "EURUSD", "XAUUSD", "--symbol", "WTI"]
    )

    assert _requested_symbols(arguments, settings) == ["EURUSD", "XAUUSD", "WTI"]


class _Profile:
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def symbols(self, visible_only: bool = ...) -> list[str]:
        return list(self._names)


class _Adapter:
    catalog: ClassVar[list[str]] = []

    def __init__(self, settings: MT5Settings) -> None:
        pass

    def __enter__(self) -> _Adapter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def symbols(self, visible_only: bool = ...) -> list[str]:
        return list(self.catalog)


def test_resolution_reports_both_broker_names_for_one_research_symbol(
    monkeypatch,
) -> None:
    """The whole point: one research name, two broker names, one report."""
    _Adapter.catalog = ["BITCOIN", "BTCUSD", "BRN", "BRENT", "EURUSD"]
    monkeypatch.setattr("market_relationship_discovery.application.commands.MT5Adapter", _Adapter)
    settings = Settings(
        brokers={
            "A": MT5Settings(symbol_mapping={"BTCUSD": "BITCOIN", "BRENT": "BRN"}),
            "B": MT5Settings(symbol_mapping={"BTCUSD": "BTCUSD", "BRENT": "BRENT"}),
        }
    )

    report = resolve_symbol_set(settings, ["A", "B"], ["BTCUSD", "BRENT", "EURUSD"])

    by_profile = {item["broker_profile"]: item["symbols"] for item in report["broker_profiles"]}
    assert by_profile["A"]["BTCUSD"]["broker_symbol"] == "BITCOIN"
    assert by_profile["B"]["BTCUSD"]["broker_symbol"] == "BTCUSD"
    assert by_profile["A"]["BRENT"]["broker_symbol"] == "BRN"
    assert by_profile["B"]["BRENT"]["broker_symbol"] == "BRENT"
    assert report["comparable_symbols"] == ["BTCUSD", "BRENT", "EURUSD"]
    assert report["unresolved"] == []


def test_an_unresolvable_symbol_is_reported_rather_than_hidden(
    monkeypatch,
) -> None:
    _Adapter.catalog = ["EURUSD"]
    monkeypatch.setattr("market_relationship_discovery.application.commands.MT5Adapter", _Adapter)
    settings = Settings(brokers={"A": MT5Settings()})

    report = resolve_symbol_set(settings, ["A"], ["EURUSD", "BTCUSD"])

    assert report["comparable_symbols"] == ["EURUSD"]
    assert len(report["unresolved"]) == 1
    assert report["unresolved"][0]["symbol"] == "BTCUSD"
    assert "unresolved" in report["summary"]


def test_a_set_requiring_no_symbols_is_refused() -> None:
    with pytest.raises(MarketRelationshipError):
        resolve_symbol_set(Settings(brokers={}), [], [])


def test_the_report_is_serializable() -> None:
    """A report that cannot be written is a report nobody reads."""
    from market_relationship_discovery.cli import _serializable

    payload = {"profiles": [{"symbols": {"XAUUSD": {"strategy": "configuration"}}}]}

    assert json.loads(_serializable(payload)) == payload
