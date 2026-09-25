from pathlib import Path

import pytest
from pydantic import ValidationError

from market_relationship_discovery.config.settings import Settings


def test_nested_environment_configuration(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        'MT5__DEMO_ONLY=true\nDATA__TIMEZONE=UTC\nSYMBOL_MAPPING={"XAUUSD":"GOLD#"}\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env)

    assert settings.mt5.demo_only is True
    assert settings.symbol_mapping["XAUUSD"] == "GOLD#"


def test_multiple_broker_profiles_are_loaded_from_local_environment(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        'BROKERS={"ALPARI":{"terminal_path":"C:\\\\demo\\\\terminal64.exe","demo_only":true}}\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env)

    assert settings.brokers["ALPARI"].demo_only is True
    assert settings.brokers["ALPARI"].terminal_path is not None
    assert settings.brokers["ALPARI"].terminal_path.name == "terminal64.exe"


def test_password_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(mt5={"password": "secret"})
