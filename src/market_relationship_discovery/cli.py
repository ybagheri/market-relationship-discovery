import argparse
import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from market_relationship_discovery.application.doctor import doctor_exit_code, run_doctor
from market_relationship_discovery.config import get_settings
from market_relationship_discovery.infrastructure.logging.config import configure_logging
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m market_relationship_discovery")
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("mt5-info")
    symbols_parser = subparsers.add_parser("symbols")
    symbols_parser.add_argument("--search", default=None)
    symbols_parser.add_argument("--all", action="store_true", help="include hidden symbols")
    subparsers.add_parser("dashboard")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    configure_logging(logging.DEBUG if arguments.verbose else logging.INFO)
    try:
        if arguments.command == "doctor":
            return _doctor()
        if arguments.command == "mt5-info":
            return _mt5_info()
        if arguments.command == "symbols":
            return _symbols(arguments.search, arguments.all)
        if arguments.command == "dashboard":
            return _dashboard()
    except Exception as exc:
        logging.getLogger("cli").exception("command_failed", extra={"command": arguments.command})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


def _doctor() -> int:
    checks = run_doctor(get_settings())
    for check in checks:
        marker = "OK" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.detail}")
    return doctor_exit_code(checks)


def _mt5_info() -> int:
    settings = get_settings()
    with MT5Adapter(settings.mt5) as adapter:
        print(
            _serializable({"terminal": adapter.terminal_info(), "account": adapter.account_info()})
        )
    return 0


def _symbols(search: str | None, include_hidden: bool) -> int:
    settings = get_settings()
    with MT5Adapter(settings.mt5) as adapter:
        symbols = adapter.symbols(visible_only=not include_hidden)
        if search:
            query = search.casefold()
            symbols = [symbol for symbol in symbols if query in symbol.casefold()]
        for symbol in sorted(symbols):
            print(symbol)
    return 0


def _dashboard() -> int:
    import subprocess
    from pathlib import Path

    settings = get_settings()
    application = Path(__file__).with_name("dashboard") / "app.py"
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(application),
            "--server.address",
            settings.dashboard.host,
            "--server.port",
            str(settings.dashboard.port),
            "--server.headless",
            "true",
        ]
    )


def _serializable(value: Any) -> str:
    def convert(item: Any) -> Any:
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        if isinstance(item, Enum):
            return item.value
        raise TypeError

    return json.dumps(value, default=convert, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
