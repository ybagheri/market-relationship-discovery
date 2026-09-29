"""A setting must either do something or be refused.

`DataSettings.timezone` took part in a critical `doctor` verdict while no data
path honoured it: every calculation is UTC regardless of the value. Setting it
to anything but UTC therefore failed a *safety* check that had nothing to do with
safety, and leaving it at UTC implied a control that did not exist.

`cache_enabled` and `cache_directory` were read by nothing at all, advertising
a cache the platform does not have.

`latency_log_statistic` was an unvalidated string. The CLI validated it, but a
value coming from configuration was accepted and then ignored by the command
that is supposed to read it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.config.settings import CostSettings, DataSettings, Settings


def test_a_non_utc_display_timezone_is_valid() -> None:
    """The setting is for display, and a local timezone is a legitimate one."""
    assert DataSettings(timezone="Asia/Tehran").timezone == "Asia/Tehran"


def test_an_unknown_timezone_is_refused_with_the_alternatives() -> None:
    with pytest.raises(ValueError) as caught:
        DataSettings(timezone="Tehran-ish")

    assert "IANA" in str(caught.value)
    assert "UTC" in str(caught.value)


def test_a_blank_timezone_is_refused() -> None:
    with pytest.raises(ValueError, match="blank"):
        DataSettings(timezone="   ")


def _demo_profile():
    from market_relationship_discovery.config.settings import MT5Settings

    return MT5Settings(terminal_path=None, data_path=None, demo_only=True)


def _configuration_check(settings: Settings):
    from market_relationship_discovery.application.doctor import _configuration_check

    return _configuration_check(_demo_profile(), settings)


def test_the_timezone_is_not_part_of_the_demo_safety_verdict() -> None:
    """A display setting must never fail a safety check.

    It previously did, so a researcher with a local timezone was told the demo
    guarantee was broken when the account mode was provably demo.
    """
    check = _configuration_check(Settings(data=DataSettings(timezone="Asia/Tehran")))

    assert check.passed is True
    assert "display_timezone=Asia/Tehran" in check.detail


def test_the_safety_verdict_still_fails_when_the_account_guarantee_is_off() -> None:
    from market_relationship_discovery.application.doctor import _configuration_check

    profile = _demo_profile().model_copy(update={"demo_only": False})

    check = _configuration_check(profile, Settings())

    assert check.passed is False


def test_the_report_states_which_timezone_it_used() -> None:
    """Otherwise a reader cannot tell what a displayed instant means."""
    check = _configuration_check(Settings(data=DataSettings(timezone="Asia/Tehran")))

    assert "Asia/Tehran" in check.detail


def test_the_display_timezone_actually_reaches_a_report() -> None:
    """The setting must do what `doctor` now says it does."""
    import pandas as pd

    from market_relationship_discovery.application.comparison import (
        CrossBrokerExperimentService,
    )

    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-25T00:00:00Z", "2026-09-25T00:00:01Z"], utc=True),
            "symbol": ["EURUSD", "EURUSD"],
            "close": [1.1, 1.2],
        }
    )
    source = _write(frame)

    utc = CrossBrokerExperimentService().run(
        source,
        source,
        "A",
        "B",
        "EURUSD",
        _bar_kind(),
        1000,
        0.0,
        display_timezone="UTC",
    )
    local = CrossBrokerExperimentService().run(
        source,
        source,
        "A",
        "B",
        "EURUSD",
        _bar_kind(),
        1000,
        0.0,
        display_timezone="Asia/Tehran",
    )

    utc_stamp = utc["results"]["aligned_preview"][0]["timestamp"]
    local_stamp = local["results"]["aligned_preview"][0]["timestamp"]

    assert utc_stamp.startswith("2026-09-25T00:00:00")
    assert local_stamp.startswith("2026-09-25T03:30:00")
    # The same instant, rendered twice.
    assert pd.Timestamp(local_stamp) == pd.Timestamp(utc_stamp)


def _bar_kind():
    from market_relationship_discovery.market_data.cross_broker import ComparisonKind

    return ComparisonKind.BAR


def _write(frame: pd.DataFrame) -> Path:
    import tempfile

    path = Path(tempfile.mkdtemp()) / "frame.csv"
    frame.to_csv(path, index=False)
    return path


def test_the_removed_cache_settings_are_gone() -> None:
    """A control the platform does not implement must not be configurable."""
    settings = DataSettings()

    assert not hasattr(settings, "cache_enabled")
    assert not hasattr(settings, "cache_directory")


def test_an_unknown_latency_statistic_is_refused() -> None:
    with pytest.raises(ValueError) as caught:
        CostSettings(latency_log_statistic="average-ish")

    assert "median" in str(caught.value)


@pytest.mark.parametrize("statistic", ["mean", "median", "p95", "maximum", "minimum"])
def test_every_known_latency_statistic_is_accepted(statistic: str) -> None:
    assert CostSettings(latency_log_statistic=statistic).latency_log_statistic == statistic


def test_a_latency_statistic_is_case_insensitive() -> None:
    assert CostSettings(latency_log_statistic="P95").latency_log_statistic == "p95"
