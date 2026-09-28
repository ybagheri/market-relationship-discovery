import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.errors import DemoSafetyError, MT5ConnectionError
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

    def terminal_info(self) -> SimpleNamespace:
        return SimpleNamespace(name="DemoTerminal", company="Demo", build=1, path="")

    def last_error(self) -> tuple[int, str]:
        return 0, "ok"

    def shutdown(self) -> bool:
        self.shutdown_called = True
        self.initialized = False
        return True

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

    def copy_ticks_range(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        flags: int,
    ) -> list[dict[str, float | int]]:
        base = time.time() - 60.0
        rows = [
            {
                "time": base + index,
                "bid": 1.1 + index / 1000,
                "ask": 1.2 + index / 1000,
                "volume": index,
            }
            for index in range(200)
        ]
        lower = start.timestamp()
        upper = end.timestamp()
        return [row for row in rows if lower <= float(row["time"]) <= upper]

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

    quotes = adapter.recent_ticks("EURUSD", datetime.now(UTC) - timedelta(hours=48), 3)

    assert len(quotes) == 3
    assert all(quote.timestamp.utcoffset() == UTC.utcoffset(quote.timestamp) for quote in quotes)
    adapter.disconnect()


def test_recent_ticks_return_the_newest_ticks_not_the_oldest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A "most recent N ticks" request must not return the oldest N in the window.

    ``copy_ticks_from`` returns the first ``count`` ticks at or after the
    requested time, so it silently selected stale data. Searching a range and
    keeping the newest rows is required for tick-level research.
    """
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    quotes = adapter.recent_ticks("EURUSD", datetime.now(UTC) - timedelta(hours=48), 5)

    assert len(quotes) == 5
    timestamps = [quote.timestamp for quote in quotes]
    assert timestamps == sorted(timestamps)
    assert quotes[-1].bid == max(quote.bid for quote in quotes)
    adapter.disconnect()


def test_recent_ticks_widen_the_window_when_data_is_sparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A closed market must not be reported as a connection failure.

    MetaTrader returns an empty array rather than ``None`` when a range holds no
    ticks, and the most recent ticks can sit well before the current time. The
    adapter widens its lookback window before giving up.
    """

    class SparseMT5(FakeMT5):
        def __init__(self) -> None:
            super().__init__(0)
            self.requested_windows: list[tuple[datetime, datetime]] = []

        def copy_ticks_range(
            self,
            symbol: str,
            start: datetime,
            end: datetime,
            flags: int,
        ) -> list[dict[str, float | int]]:
            self.requested_windows.append((start, end))
            rows = super().copy_ticks_range(symbol, start, end, flags)
            return rows if len(self.requested_windows) > 2 else []

    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = SparseMT5()
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    quotes = adapter.recent_ticks("EURUSD", datetime.now(UTC) - timedelta(days=30), 3)

    assert len(quotes) == 3
    assert len(fake.requested_windows) > 1
    adapter.disconnect()


def test_recent_ticks_report_a_closed_market_clearly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClosedMT5(FakeMT5):
        def copy_ticks_range(
            self,
            symbol: str,
            start: datetime,
            end: datetime,
            flags: int,
        ) -> list[dict[str, float | int]]:
            return []

    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module",
        lambda _: ClosedMT5(0),
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    with pytest.raises(MT5ConnectionError, match="market may be closed"):
        adapter.recent_ticks("EURUSD", datetime.now(UTC) - timedelta(days=30), 3)

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


def test_the_demo_guarantee_is_reverified_after_the_cache_ages_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal re-logged-in mid-session must not keep reporting DEMO.

    The account check is a time-of-check and the terminal is a separate
    long-lived process, so a snapshot cached for the life of the adapter would
    keep certifying an account the operator has already switched away from. The
    snapshot is also written into every dataset manifest.
    """
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal, account_verification_ttl_seconds=1))
    adapter.connect()
    assert adapter.account_info().mode == "DEMO"

    # The operator switches the terminal to a live account without restarting it.
    fake.trade_mode = 1
    assert adapter.account_info().mode == "DEMO", "a fresh verification is still cached"

    adapter._verified_at = datetime.now(UTC) - timedelta(seconds=120)

    with pytest.raises(DemoSafetyError):
        adapter.account_info()
    assert fake.shutdown_called is True


def test_a_dead_terminal_is_not_reported_as_connected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``is_connected`` must not mean only that an import succeeded."""
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()
    assert adapter.is_connected is True

    fake.terminal_info = lambda: None

    assert adapter.is_connected is False
    adapter.disconnect()
    assert adapter.is_connected is False


def test_reconnecting_does_not_keep_the_previous_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second connect must not verify a handle left over from the first."""
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"")
    fake = FakeMT5(0)
    monkeypatch.setattr(
        "market_relationship_discovery.infrastructure.mt5.adapter.import_module", lambda _: fake
    )
    adapter = MT5Adapter(MT5Settings(terminal_path=terminal))
    adapter.connect()

    adapter.connect()

    # The stale session was shut down before the new one was opened.
    assert fake.shutdown_called is True
    adapter.disconnect()
