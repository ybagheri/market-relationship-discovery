"""Two labels for one terminal are not two brokers.

Two broker profiles pointing at the same executable produce two directories of
what is one feed, and a cross-broker comparison can then pair a broker with
itself and report the difference between a feed and a copy of it. Neither
`doctor` nor the collector notices, because each profile is individually
healthy and individually connects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from market_relationship_discovery.config import get_settings
from market_relationship_discovery.config.settings import MT5Settings, Settings


@pytest.fixture(autouse=True)
def _isolated_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Build settings from arguments alone, never from a local `.env`.

    The repository's own `.env` configures two live demo terminals, and reading
    it here would merge those profiles into every case below and make a test
    about duplicate detection depend on the developer's machine.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("", encoding="utf-8")
    for name in ("BROKERS", "MT5__TERMINAL_PATH", "MT5__DATA_PATH"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()


def _profile(path: str | None) -> MT5Settings:
    return MT5Settings(terminal_path=Path(path) if path else None)


def test_two_profiles_on_one_terminal_are_refused() -> None:
    with pytest.raises(ValueError) as caught:
        Settings(
            brokers={
                "ALPARI_1": _profile("C:/terminals/a/terminal64.exe"),
                "ALPARI_2": _profile("C:/terminals/a/terminal64.exe"),
            }
        )

    message = str(caught.value)
    assert "ALPARI_1" in message and "ALPARI_2" in message
    assert "different terminals" in message


def test_the_error_says_why_it_matters() -> None:
    """A configuration error a reader cannot act on is half an error."""
    with pytest.raises(ValueError) as caught:
        Settings(
            brokers={
                "A": _profile("C:/terminals/a/terminal64.exe"),
                "B": _profile("C:/terminals/a/terminal64.exe"),
            }
        )

    assert "with itself" in str(caught.value)


def test_two_spellings_of_one_path_are_still_one_terminal() -> None:
    """Case and separator differences must not hide the collision."""
    with pytest.raises(ValueError, match="different terminals"):
        Settings(
            brokers={
                "A": _profile("C:/terminals/a/terminal64.exe"),
                "B": _profile(r"c:\TERMINALS\a\TERMINAL64.EXE"),
            }
        )


def test_distinct_terminals_are_accepted() -> None:
    settings = Settings(
        brokers={
            "A": _profile("C:/terminals/a/terminal64.exe"),
            "B": _profile("C:/terminals/b/terminal64.exe"),
        }
    )

    assert set(settings.brokers) == {"A", "B"}


def test_a_profile_with_no_terminal_is_not_a_duplicate() -> None:
    """An unfilled profile is incomplete configuration, not a collision."""
    settings = Settings(brokers={"A": _profile(None), "B": _profile(None)})

    assert set(settings.brokers) == {"A", "B"}


def test_the_default_profile_may_share_a_terminal_with_a_named_one() -> None:
    """`default` is an alias for one terminal, not a second broker.

    A single-broker setup configures both, and refusing that would make the
    default profile unusable for everyone who adds a named profile later.
    """
    settings = Settings(brokers={"ALPARI_1": _profile("C:/terminals/a/terminal64.exe")})
    settings.mt5.terminal_path = Path("C:/terminals/a/terminal64.exe")

    assert "ALPARI_1" in settings.brokers


def test_the_real_two_broker_configuration_is_accepted() -> None:
    """The observed Alpari and AMarkets demo pair must load."""
    settings = Settings(
        brokers={
            "ALPARI_1": _profile("C:/Users/bagheri/AppData/Roaming/Alpari MT5/terminal64.exe"),
            "ALPARI_2": _profile("C:/Users/bagheri/AppData/Roaming/Alpari MT5_2/terminal64.exe"),
        }
    )

    assert len(settings.brokers) == 2


def test_an_unresolvable_path_does_not_crash_the_check() -> None:
    """A path that cannot be resolved is still comparable as written."""
    settings = Settings(
        brokers={
            "A": _profile("Z:/does/not/exist/terminal64.exe"),
            "B": _profile("Y:/also/missing/terminal64.exe"),
        }
    )

    assert len(settings.brokers) == 2


def test_the_cli_states_a_refused_configuration_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A traceback buries the message under pydantic's echo of the input.

    The adapter is stubbed because the configuration is refused before any
    terminal is contacted; without that, `doctor` would launch a real MT5
    terminal on a machine where one is installed, and the test would take the
    time it takes to start and stop a terminal.
    """
    from market_relationship_discovery.cli import main

    monkeypatch.setenv(
        "BROKERS",
        '{"A":{"terminal_path":"C:/T/terminal64.exe"},'
        '"B":{"terminal_path":"C:/T/terminal64.exe"}}',
    )
    # Settings are cached for the life of the process, so a value cached by an
    # earlier test would be read instead of the environment this test set.
    get_settings.cache_clear()

    class _Refused:
        def __init__(self, settings: object) -> None:
            pass

        def __enter__(self) -> _Refused:
            raise AssertionError("the terminal must not be contacted")

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("market_relationship_discovery.application.doctor.MT5Adapter", _Refused)

    code = main(["doctor"])
    captured = capsys.readouterr()
    get_settings.cache_clear()

    assert code == 1
    assert "CONFIGURATION ERROR" in captured.err
    assert "different terminals" in captured.err
    assert "Traceback" not in captured.err
    assert "input_value" not in captured.err
