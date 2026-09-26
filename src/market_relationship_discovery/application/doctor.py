import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from market_relationship_discovery.application.commands import resolve_profile
from market_relationship_discovery.config.settings import MT5Settings, Settings
from market_relationship_discovery.domain.errors import (
    DemoSafetyError,
    MT5ConnectionError,
    SymbolNotFoundError,
)
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.market_data.symbols import SymbolMapper


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    critical: bool = False


def run_doctor(settings: Settings, broker_profile: str = "default") -> list[CheckResult]:
    """Diagnose the environment for one broker profile.

    Diagnostics are profile aware so that every configured terminal can be
    verified independently. A passing check on one profile says nothing about
    another, which matters once several demo terminals are configured.
    """
    profile, symbol_mapping = resolve_profile(settings, broker_profile)
    label = f" [{broker_profile}]" if broker_profile != "default" else ""
    checks = [
        _python_check(),
        _package_check("MetaTrader5", "MetaTrader5"),
        _path_check(f"MT5 data path{label}", profile.data_path, directory=True),
        _terminal_check(profile.terminal_path, label),
        _writable_check(settings.data.processed_directory),
        _configuration_check(profile, settings, label),
    ]
    adapter: MT5Adapter | None = None
    try:
        adapter = MT5Adapter(profile)
        adapter.connect()
        account = adapter.account_info()
        terminal = adapter.terminal_info()
        checks.append(CheckResult(f"MT5 connection{label}", True, "connected", True))
        checks.append(
            CheckResult(
                f"Account mode{label}",
                account.mode == "DEMO",
                account.mode,
                True,
            )
        )
        checks.append(CheckResult(f"Account server{label}", True, account.server, True))
        checks.append(
            CheckResult(
                f"MT5 terminal info{label}",
                True,
                f"{terminal.name} build {terminal.build}",
            )
        )
        symbols = adapter.symbols(visible_only=False)
        checks.append(_symbol_check("Relevant symbol discovery", symbols, symbol_mapping, label))
    except (MT5ConnectionError, DemoSafetyError, ValueError) as exc:
        checks.append(CheckResult(f"MT5 connection{label}", False, str(exc), True))
    finally:
        if adapter is not None:
            adapter.disconnect()
    return checks


def doctor_exit_code(checks: list[CheckResult]) -> int:
    return int(any(check.critical and not check.passed for check in checks))


def _python_check() -> CheckResult:
    supported = sys.version_info >= (3, 12)
    return CheckResult("Python", supported, sys.version.split()[0], True)


def _package_check(import_name: str, display_name: str) -> CheckResult:
    available = find_spec(import_name) is not None
    return CheckResult(
        f"{display_name} package", available, "installed" if available else "missing", True
    )


def _terminal_check(path: Path | None, label: str = "") -> CheckResult:
    if path is None:
        return CheckResult(f"MT5 terminal{label}", False, "not configured", True)
    exists = path.is_file()
    return CheckResult(
        f"MT5 terminal{label}", exists, str(path) if exists else f"missing: {path}", True
    )


def _path_check(name: str, path: Path | None, directory: bool) -> CheckResult:
    if path is None:
        return CheckResult(name, False, "not configured")
    valid = path.is_dir() if directory else path.is_file()
    return CheckResult(name, valid, str(path) if valid else f"missing: {path}")


def _writable_check(path: Path) -> CheckResult:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult("Storage write permission", False, str(exc), True)
    return CheckResult("Storage write permission", True, str(path))


def _configuration_check(
    profile: MT5Settings,
    settings: Settings,
    label: str = "",
) -> CheckResult:
    valid = profile.demo_only and settings.data.timezone.upper() == "UTC"
    detail = f"demo_only={profile.demo_only}; timezone={settings.data.timezone}"
    return CheckResult(f"Configuration safety{label}", valid, detail, True)


def _symbol_check(
    name: str,
    symbols: list[str],
    symbol_mapping: dict[str, str],
    label: str = "",
) -> CheckResult:
    """Report which canonical research symbols the broker can actually serve.

    Resolution goes through :class:`SymbolMapper` so a broker-specific name such
    as ``BITCOIN`` for ``BTCUSD`` is reported as available rather than missing.
    """
    required = sorted(symbol_mapping) or ["EURUSD", "GBPUSD", "XAUUSD"]
    mapper = SymbolMapper(symbol_mapping)
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for canonical in required:
        try:
            resolved[canonical] = mapper.resolve(canonical, symbols).broker_symbol
        except SymbolNotFoundError:
            unresolved.append(canonical)
    detail = f"resolved {len(resolved)} of {len(required)}"
    if resolved:
        detail += f": {', '.join(f'{k}->{v}' for k, v in sorted(resolved.items()))}"
    if unresolved:
        detail += f"; unavailable: {', '.join(unresolved)}"
    return CheckResult(f"{name}{label}", bool(resolved), detail)
