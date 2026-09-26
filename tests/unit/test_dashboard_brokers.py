"""Tests for the multi-broker dashboard layer.

The dashboard previously requested quotes using canonical research names, which
fails on any broker that publishes an instrument under a different label. These
tests pin the resolution behaviour without opening a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from market_relationship_discovery.config.settings import MT5Settings, Settings
from market_relationship_discovery.dashboard.brokers import (
    DEFAULT_PROFILE,
    MAX_MONITOR_SYMBOLS,
    ProfileStatus,
    configured_profiles,
    profile_health,
    quote_rows,
    resolve_monitor_symbols,
)
from market_relationship_discovery.domain.market import Quote
from market_relationship_discovery.infrastructure.mt5.adapter import AccountSnapshot

ALPARI_A_SYMBOLS = ["XAUUSD", "XAGUSD", "XAUEUR", "EURUSD", "GBPUSD", "USDJPY", "BITCOIN"]
ALPARI_B_SYMBOLS = ["XAUUSD", "XAGUSD", "XAUEUR", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]


@dataclass
class FakeAdapter:
    available: list[str] = field(default_factory=list)
    requested: list[str] = field(default_factory=list)

    def __enter__(self) -> FakeAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def account_info(self) -> AccountSnapshot:
        return AccountSnapshot("DEMO", "DemoServer", "USD", 500)

    def terminal_info(self) -> object:
        return type("Terminal", (), {"name": "Alpari MT5", "build": 6184})()

    def symbols(self, visible_only: bool = False) -> list[str]:
        return list(self.available)

    def current_quote(self, symbol: str) -> Quote:
        self.requested.append(symbol)
        return Quote.create(
            datetime(2026, 9, 26, tzinfo=UTC),
            "DemoServer",
            symbol,
            1.0,
            1.1,
            "test",
        )


def settings_with_two_brokers() -> Settings:
    return Settings(
        _env_file=None,
        mt5={"terminal_path": None},
        brokers={
            "ALPARI_1": MT5Settings(symbol_mapping={"XAUUSD": "XAUUSD", "BTCUSD": "BITCOIN"}),
            "ALPARI_2": MT5Settings(symbol_mapping={"XAUUSD": "XAUUSD", "BTCUSD": "BTCUSD"}),
        },
        symbol_mapping={"XAUUSD": "XAUUSD", "BTCUSD": "BTCUSD"},
    )


def test_default_profile_is_always_offered() -> None:
    references = configured_profiles(Settings(_env_file=None, mt5={"terminal_path": None}))

    assert len(references) == 1
    assert references[0].name == DEFAULT_PROFILE
    assert references[0].is_default is True


def test_every_configured_broker_is_listed_with_the_default_first() -> None:
    references = configured_profiles(settings_with_two_brokers())

    assert [item.name for item in references] == [DEFAULT_PROFILE, "ALPARI_1", "ALPARI_2"]
    assert [item.is_default for item in references] == [True, False, False]
    assert all(item.demo_only for item in references)


def test_per_profile_symbol_mapping_resolves_broker_specific_labels() -> None:
    """One broker publishes bitcoin as BITCOIN and the other as BTCUSD."""
    profile = MT5Settings(symbol_mapping={"XAUUSD": "XAUUSD", "BTCUSD": "BITCOIN"})

    resolved, missing = resolve_monitor_symbols(
        profile,
        {},
        ALPARI_A_SYMBOLS,
    )
    by_canonical = {item.canonical: item.broker_symbol for item in resolved}

    assert by_canonical["BTCUSD"] == "BITCOIN"
    assert by_canonical["XAUUSD"] == "XAUUSD"
    assert missing == ()


def test_shared_mapping_is_used_when_a_profile_has_none() -> None:
    resolved, _ = resolve_monitor_symbols(
        MT5Settings(),
        {"XAUUSD": "XAUUSD"},
        ALPARI_A_SYMBOLS,
    )

    assert [item.broker_symbol for item in resolved] == ["XAUUSD"]


def test_symbols_the_broker_does_not_offer_are_reported_not_hidden() -> None:
    resolved, missing = resolve_monitor_symbols(
        MT5Settings(symbol_mapping={"XAUUSD": "XAUUSD", "EURJPY": "EURJPY"}),
        {},
        ALPARI_A_SYMBOLS,
    )

    assert [item.canonical for item in resolved] == ["XAUUSD"]
    assert missing == ("EURJPY",)


def test_monitor_limit_is_respected() -> None:
    mapping = {f"S{index}": f"S{index}" for index in range(MAX_MONITOR_SYMBOLS + 5)}
    available = list(mapping)

    resolved, _ = resolve_monitor_symbols(MT5Settings(symbol_mapping=mapping), {}, available)

    assert len(resolved) == MAX_MONITOR_SYMBOLS


def test_each_broker_resolves_bitcoin_to_its_own_label() -> None:
    broker_a, _ = resolve_monitor_symbols(
        MT5Settings(symbol_mapping={"BTCUSD": "BITCOIN"}),
        {},
        ALPARI_A_SYMBOLS,
    )
    broker_b, _ = resolve_monitor_symbols(
        MT5Settings(symbol_mapping={"BTCUSD": "BTCUSD"}),
        {},
        ALPARI_B_SYMBOLS,
    )

    assert broker_a[0].broker_symbol == "BITCOIN"
    assert broker_b[0].broker_symbol == "BTCUSD"


def test_quote_rows_request_each_broker_symbol_exactly_once() -> None:
    """The previous monitor asked for each quote three times per row."""
    adapter = FakeAdapter(available=ALPARI_A_SYMBOLS)
    resolved, _ = resolve_monitor_symbols(
        MT5Settings(symbol_mapping={"XAUUSD": "XAUUSD", "BTCUSD": "BITCOIN"}),
        {},
        ALPARI_A_SYMBOLS,
    )

    rows = quote_rows(adapter, resolved)

    assert adapter.requested == ["XAUUSD", "BITCOIN"]
    assert [row["Canonical"] for row in rows] == ["XAUUSD", "BTCUSD"]
    assert rows[0]["Bid"] == 1.0
    assert rows[0]["Ask"] == 1.1
    assert rows[0]["Mid"] == pytest.approx(1.05)


def test_health_reports_a_failure_instead_of_raising() -> None:
    health = profile_health(Settings(_env_file=None, mt5={"terminal_path": None}), "does-not-exist")

    assert health.status is ProfileStatus.FAILED
    assert health.is_demo is False
    assert "does-not-exist" in health.detail


def test_health_reports_an_unconfigured_profile() -> None:
    health = profile_health(Settings(_env_file=None, mt5={"terminal_path": None}), DEFAULT_PROFILE)

    assert health.status is ProfileStatus.NOT_CONFIGURED
    assert health.is_demo is False


def test_health_payload_is_serializable() -> None:
    health = profile_health(Settings(_env_file=None, mt5={"terminal_path": None}), DEFAULT_PROFILE)

    payload = health.to_dict()

    assert payload["profile"] == DEFAULT_PROFILE
    assert payload["status"] == ProfileStatus.NOT_CONFIGURED.value
