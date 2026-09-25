from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.errors import DemoSafetyError
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 4

    def __init__(self, trade_mode: int) -> None:
        self.trade_mode = trade_mode
        self.initialized = False
        self.shutdown_called = False

    def initialize(self, **_: object) -> bool:
        self.initialized = True
        return True

    def shutdown(self) -> None:
        self.shutdown_called = True
        self.initialized = False

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(
            trade_mode=self.trade_mode,
            server="DemoServer",
            currency="USD",
            leverage=100,
        )

    def copy_ticks_from(
        self,
        symbol: str,
        start: object,
        count: int,
        flags: int,
    ) -> list[dict[str, float | int]]:
        return [
            {
                "time": 1789680000 + index,
                "bid": 1.1 + index / 1000,
                "ask": 1.2 + index / 1000,
                "volume": index,
            }
            for index in range(count)
        ]

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(
            name=symbol,
            description="EURUSD",
            path="Forex\\EURUSD",
            currency_base="EUR",
            currency_profit="USD",
            digits=5,
            point=0.00001,
            spread=10,
            trade_mode=4,
            trade_contract_size=100000.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            trade_tick_size=0.00001,
            trade_tick_value_profit=1.0,
            margin_initial=0.0,
        )

    def last_error(self) -> tuple[int, str]:
        return 0, "ok"


def test_demo_account_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))

    adapter.connect()

    assert adapter.account_info().mode == "DEMO"
    adapter.disconnect()
    assert fake.shutdown_called is True


def test_recent_ticks_are_normalized_to_utc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    quotes = adapter.recent_ticks("EURUSD", datetime.now(UTC), 3)

    assert len(quotes) == 3
    assert all(quote.timestamp.utcoffset() == UTC.utcoffset(quote.timestamp) for quote in quotes)
    adapter.disconnect()


def test_contract_specification_reads_official_mt5_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    specification = adapter.contract_specification("EURUSD")

    assert specification.contract_size == 100000.0
    assert specification.tick_value == 1.0
    assert specification.volume_step == 0.01
    adapter.disconnect()


def test_unknown_account_mode_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(99)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))

    with pytest.raises(DemoSafetyError):
        adapter.connect()

    assert fake.shutdown_called is True
