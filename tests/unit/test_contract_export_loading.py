"""A `symbol-specs` export must be usable by `compare-brokers`.

`symbol-specs` writes a list, one entry per requested symbol. `compare-brokers`
accepted that list only when it held exactly one entry, so exporting specs for
the several symbols a cross-broker study needs produced a file the comparison
rejected with "must contain exactly one specification" — an export that is
completely valid reported as corrupt.

Found against the live Alpari/AMarkets demo pair, where the four-symbol export
could not be used for any comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_relationship_discovery.application.comparison import (
    CrossBrokerExperimentService,
)
from market_relationship_discovery.market_data.contract import ContractSpecification

SPECS = [
    {
        "broker": "A",
        "server": "S",
        "symbol": name,
        "description": name,
        "path": f"p\\{name}",
        "currency_base": "EUR",
        "currency_profit": "USD",
        "digits": 5,
        "point": 0.00001,
        "spread": 10,
        "trade_mode": 4,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "margin_initial": 0.0,
    }
    for name in ("EURUSD", "GBPUSD", "WTI", "XAUUSD")
]


@pytest.fixture()
def export(tmp_path: Path) -> Path:
    path = tmp_path / "specs.json"
    path.write_text(json.dumps(SPECS), encoding="utf-8")
    return path


def _load(service: CrossBrokerExperimentService, path: Path, symbol: str) -> str:
    loaded = service._load_contract(path, symbol)
    assert loaded is not None
    return loaded.symbol


def test_the_compared_symbol_selects_its_specification(
    export: Path,
) -> None:
    service = CrossBrokerExperimentService()

    assert _load(service, export, "WTI") == "WTI"
    assert _load(service, export, "XAUUSD") == "XAUUSD"


def test_selection_is_case_insensitive_like_every_other_symbol_lookup(
    export: Path,
) -> None:
    assert _load(CrossBrokerExperimentService(), export, "eurusd") == "EURUSD"


def test_an_absent_symbol_names_what_the_file_actually_contains(
    export: Path,
) -> None:
    """A missing symbol must say which symbols are available.

    Reporting "exactly one specification" for a four-symbol file sent the reader
    looking for a corrupt export rather than for the wrong symbol name.
    """
    with pytest.raises(ValueError) as caught:
        CrossBrokerExperimentService()._load_contract(export, "USDJPY")

    message = str(caught.value)
    assert "USDJPY" in message
    assert "WTI" in message


def test_a_single_entry_file_still_loads_without_a_symbol(tmp_path: Path) -> None:
    path = tmp_path / "one.json"
    path.write_text(json.dumps([SPECS[0]]), encoding="utf-8")

    loaded = CrossBrokerExperimentService()._load_contract(path)

    assert isinstance(loaded, ContractSpecification)
    assert loaded.symbol == "EURUSD"


def test_an_ambiguous_file_without_a_symbol_is_refused_clearly(
    tmp_path: Path,
) -> None:
    path = tmp_path / "many.json"
    path.write_text(json.dumps(SPECS), encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        CrossBrokerExperimentService()._load_contract(path)

    assert "4 specifications" in str(caught.value)


def test_a_file_with_no_specification_objects_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(ValueError, match="no specification objects"):
        CrossBrokerExperimentService()._load_contract(path, "EURUSD")
