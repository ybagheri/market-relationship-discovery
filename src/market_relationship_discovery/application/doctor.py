import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from market_relationship_discovery.config.settings import Settings
from market_relationship_discovery.domain.errors import DemoSafetyError, MT5ConnectionError
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    critical: bool = False


def run_doctor(settings: Settings) -> list[CheckResult]:
    checks = [
        _python_check(),
        _package_check("MetaTrader5", "MetaTrader5"),
        _path_check("MT5 data path", settings.mt5.data_path, directory=True),
        _terminal_check(settings.mt5.terminal_path),
        _writable_check(settings.data.processed_directory),
        _configuration_check(settings),
    ]
    adapter: MT5Adapter | None = None
    try:
        adapter = MT5Adapter(settings.mt5)
        adapter.connect()
        account = adapter.account_info()
        terminal = adapter.terminal_info()
        checks.append(CheckResult("MT5 connection", True, "connected", True))
        checks.append(
            CheckResult(
                "Account mode",
                account.mode == "DEMO",
                account.mode,
                True,
            )
        )
        checks.append(
            CheckResult("MT5 terminal info", True, f"{terminal.name} build {terminal.build}")
        )
        symbols = adapter.symbols(visible_only=False)
        checks.append(_symbol_check("Relevant symbol discovery", symbols, settings))
    except (MT5ConnectionError, DemoSafetyError, ValueError) as exc:
        checks.append(CheckResult("MT5 connection", False, str(exc), True))
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


def _terminal_check(path: Path | None) -> CheckResult:
    if path is None:
        return CheckResult("MT5 terminal", False, "not configured", True)
    exists = path.is_file()
    return CheckResult("MT5 terminal", exists, str(path) if exists else f"missing: {path}", True)


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


def _configuration_check(settings: Settings) -> CheckResult:
    valid = settings.mt5.demo_only and settings.data.timezone.upper() == "UTC"
    detail = f"demo_only={settings.mt5.demo_only}; timezone={settings.data.timezone}"
    return CheckResult("Configuration safety", valid, detail, True)


def _symbol_check(name: str, symbols: list[str], settings: Settings) -> CheckResult:
    required = set(settings.symbol_mapping) or {"EURUSD", "GBPUSD", "XAUUSD"}
    available = {symbol.upper() for symbol in symbols}
    resolved = {canonical for canonical in required if canonical.upper() in available}
    return CheckResult(name, bool(resolved), f"matched {sorted(resolved)} of {sorted(required)}")
