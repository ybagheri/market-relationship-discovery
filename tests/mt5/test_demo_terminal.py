import pytest

from market_relationship_discovery.config import get_settings
from market_relationship_discovery.domain.errors import MT5ConnectionError
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter

pytestmark = pytest.mark.mt5


def test_configured_demo_terminal_is_available() -> None:
    try:
        with MT5Adapter(get_settings().mt5) as adapter:
            account = adapter.account_info()
            terminal = adapter.terminal_info()
            symbols = adapter.symbols()
            recent_bars = adapter.recent_bars("EURUSD", "M1", 3)
    except MT5ConnectionError as exc:
        pytest.skip(str(exc))

    assert account.mode == "DEMO"
    assert terminal.build >= 1
    assert "EURUSD" in symbols
    assert len(recent_bars) == 3
