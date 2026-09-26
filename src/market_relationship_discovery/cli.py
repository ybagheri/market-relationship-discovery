from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from market_relationship_discovery.application.commands import (
    collect_historical_data,
    discover_relationships,
    resolve_profile,
    run_advanced_research,
    run_historical_research,
    run_no_lookahead_backtest,
)
from market_relationship_discovery.application.comparison import CrossBrokerExperimentService
from market_relationship_discovery.application.doctor import doctor_exit_code, run_doctor
from market_relationship_discovery.application.experiments import (
    ResearchExperimentService,
    build_signal_stages,
)
from market_relationship_discovery.backtesting.monte_carlo import (
    STRESS_SCENARIOS,
    MonteCarloConfig,
)
from market_relationship_discovery.backtesting.walk_forward import WalkForwardConfig
from market_relationship_discovery.config import get_settings
from market_relationship_discovery.domain.dataset import DataType
from market_relationship_discovery.infrastructure.logging.config import configure_logging
from market_relationship_discovery.infrastructure.mt5.adapter import MT5Adapter
from market_relationship_discovery.market_data.cross_broker import (
    ComparisonKind,
    SynchronizationMode,
    TickAggregation,
)
from market_relationship_discovery.market_data.symbols import (
    SymbolMapper,
    SymbolSearchService,
    describe_matches,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m market_relationship_discovery")
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor")
    subparsers.add_parser("mt5-info")
    symbols_parser = subparsers.add_parser(
        "symbols",
        help=(
            "discover broker symbols by name, description, or alias "
            "(for example --search gold, --search silver, --search dollar)"
        ),
    )
    symbols_parser.add_argument("--broker-profile", default="default")
    symbols_parser.add_argument("--search", default=None)
    symbols_parser.add_argument(
        "--visible-only",
        action="store_true",
        help="restrict to symbols shown in the terminal watch window",
    )
    symbols_parser.add_argument(
        "--all",
        action="store_true",
        help="include symbols the broker marks as not tradable",
    )
    symbols_parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument("--broker-profile", action="append")
    collect_parser.add_argument("--symbol", action="append", required=True)
    collect_parser.add_argument("--data-type", choices=["tick", "bar"], default="bar")
    collect_parser.add_argument("--timeframe")
    collect_parser.add_argument("--start", help="ISO-8601 timestamp with timezone")
    collect_parser.add_argument("--end", help="ISO-8601 timestamp with timezone")
    collect_parser.add_argument("--limit", type=int)
    collect_parser.add_argument("--parallel", action="store_true")
    collect_parser.add_argument("--max-workers", type=int)
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--symbol", nargs="+", action="append")
    discover_parser.add_argument("--minimum-observations", type=int, default=100)
    discover_parser.add_argument("--input", type=Path)
    discover_parser.add_argument("--output", type=Path)
    discover_parser.add_argument("--regime-window", type=int, default=20)
    discover_parser.add_argument("--regime-low-quantile", type=float, default=0.20)
    discover_parser.add_argument("--regime-high-quantile", type=float, default=0.80)
    discover_parser.add_argument("--max-depth", type=int, default=1)
    discover_parser.add_argument("--training-fraction", type=float, default=0.70)
    discover_parser.add_argument("--ridge-alpha", type=float, default=1.0)
    discover_parser.add_argument("--rolling-beta-window", type=int, default=30)
    discover_parser.add_argument("--statistical-significance", type=float, default=0.05)
    research_parser = subparsers.add_parser("research")
    research_parser.add_argument("--broker-profile", default="default")
    research_parser.add_argument("--relationship", default="XAUEUR_SYNTHETIC")
    research_parser.add_argument("--timeframe", default="M1")
    research_parser.add_argument("--limit", type=int, default=500)
    research_parser.add_argument("--rolling-beta-window", type=int)
    research_parser.add_argument("--statistical-significance", type=float)
    backtest_parser = subparsers.add_parser("backtest")
    backtest_parser.add_argument("file", type=Path)
    backtest_parser.add_argument("--signal-column", default="signal")
    backtest_parser.add_argument("--gross-edge-column", default="gross_edge")
    backtest_parser.add_argument("--cost-column", default="cost")
    backtest_parser.add_argument("--output", type=Path)
    multi_parser = subparsers.add_parser("multi-backtest")
    multi_parser.add_argument("file", type=Path)
    multi_parser.add_argument("--stage-column", action="append", required=True)
    multi_parser.add_argument("--stage-weight", action="append", type=float)
    multi_parser.add_argument("--stage-threshold", action="append", type=float)
    multi_parser.add_argument("--ensemble-threshold", type=float, default=0.0)
    multi_parser.add_argument("--gross-edge-column", default="gross_edge")
    multi_parser.add_argument("--cost-column", default="cost")
    multi_parser.add_argument("--output", type=Path)
    walk_parser = subparsers.add_parser("walk-forward")
    walk_parser.add_argument("file", type=Path)
    walk_parser.add_argument("--signal-column", default="signal")
    walk_parser.add_argument("--gross-edge-column", default="gross_edge")
    walk_parser.add_argument("--cost-column", default="cost")
    walk_parser.add_argument("--train-size", type=int, default=252)
    walk_parser.add_argument("--validation-size", type=int, default=63)
    walk_parser.add_argument("--test-size", type=int, default=63)
    walk_parser.add_argument("--step", type=int)
    walk_parser.add_argument("--threshold", action="append", type=float)
    walk_parser.add_argument("--minimum-train-observations", type=int, default=20)
    walk_parser.add_argument("--output", type=Path)
    robustness_parser = subparsers.add_parser("robustness")
    robustness_parser.add_argument("file", type=Path)
    robustness_parser.add_argument("--signal-column", default="signal")
    robustness_parser.add_argument("--gross-edge-column", default="gross_edge")
    robustness_parser.add_argument("--cost-column", default="cost")
    robustness_parser.add_argument("--simulations", type=int, default=1000)
    robustness_parser.add_argument("--confidence-level", type=float, default=0.95)
    robustness_parser.add_argument("--seed", type=int, default=42)
    robustness_parser.add_argument("--block-size", type=int, default=1)
    robustness_parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(STRESS_SCENARIOS),
    )
    robustness_parser.add_argument("--return-shock-std", type=float, default=0.0)
    robustness_parser.add_argument("--output", type=Path)
    comparison_parser = subparsers.add_parser("compare-brokers")
    comparison_parser.add_argument("source_a", type=Path)
    comparison_parser.add_argument("source_b", type=Path)
    comparison_parser.add_argument("--broker-a", required=True)
    comparison_parser.add_argument("--broker-b", required=True)
    comparison_parser.add_argument("--symbol", required=True)
    comparison_parser.add_argument("--kind", choices=["tick", "bar"], default="tick")
    comparison_parser.add_argument("--max-delay-ms", type=int, default=100)
    comparison_parser.add_argument("--additional-cost", type=float, default=0.0)
    comparison_parser.add_argument("--contract-a", type=Path)
    comparison_parser.add_argument("--contract-b", type=Path)
    comparison_parser.add_argument(
        "--sync-mode",
        choices=["anchor_a", "symmetric"],
        default="anchor_a",
    )
    comparison_parser.add_argument(
        "--tick-aggregation",
        choices=["last", "none"],
        default="last",
    )
    comparison_parser.add_argument("--output", type=Path)
    specifications_parser = subparsers.add_parser("symbol-specs")
    specifications_parser.add_argument("--broker-profile", default="default")
    specifications_parser.add_argument("--symbol", action="append", required=True)
    specifications_parser.add_argument("--output", type=Path)
    subparsers.add_parser("dashboard")
    return parser


def _configure_console_encoding() -> None:
    """Make CLI output safe on narrow console code pages.

    Broker symbol descriptions routinely contain non-ASCII text, and Windows
    consoles default to a legacy code page such as cp1252 or cp1256. Without
    this, printing a discovered description raises ``UnicodeEncodeError`` and
    hides the discovery result the user asked for.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            continue


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    _configure_console_encoding()
    configure_logging(logging.DEBUG if arguments.verbose else logging.INFO)
    try:
        if arguments.command == "doctor":
            return _doctor()
        if arguments.command == "mt5-info":
            return _mt5_info()
        if arguments.command == "symbols":
            return _symbols(
                arguments.broker_profile,
                arguments.search,
                arguments.visible_only,
                arguments.all,
                arguments.json,
            )
        if arguments.command == "collect":
            return _collect(arguments)
        if arguments.command == "discover":
            return _discover(arguments)
        if arguments.command == "research":
            return _research(arguments)
        if arguments.command == "backtest":
            return _backtest(arguments)
        if arguments.command == "multi-backtest":
            return _multi_backtest(arguments)
        if arguments.command == "walk-forward":
            return _walk_forward(arguments)
        if arguments.command == "robustness":
            return _robustness(arguments)
        if arguments.command == "compare-brokers":
            return _compare_brokers(arguments)
        if arguments.command == "symbol-specs":
            return _symbol_specs(arguments)
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


def _symbols(
    broker_profile: str,
    search: str | None,
    visible_only: bool,
    include_disabled: bool,
    as_json: bool,
) -> int:
    """List broker symbols with metadata and the rule that matched the query.

    Discovery defaults to the full broker catalog filtered to tradable symbols.
    A broker can expose hundreds of symbols while only a handful appear in the
    terminal watch window, so restricting the search to the watch window would
    hide instruments such as gold on brokers that name them ``XAUUSD``.
    """
    settings = get_settings()
    profile, _ = resolve_profile(settings, broker_profile)
    with MT5Adapter(profile) as adapter:
        service = SymbolSearchService(adapter)
        catalog = service.catalog(visible_only=visible_only)
        results = service.search(
            search,
            visible_only=visible_only,
            tradable_only=not include_disabled,
        )
        if as_json:
            print(
                _serializable(
                    {
                        "broker_profile": broker_profile,
                        "query": search,
                        "catalog_size": len(catalog),
                        "tradable_count": sum(1 for item in catalog if item.is_tradable),
                        "match_count": len(results),
                        "symbols": [
                            {
                                "name": result.descriptor.name,
                                "description": result.descriptor.description,
                                "currency_base": result.descriptor.currency_base,
                                "currency_profit": result.descriptor.currency_profit,
                                "digits": result.descriptor.digits,
                                "point": result.descriptor.point,
                                "spread_points": result.descriptor.spread_in_points,
                                "trade_mode": result.descriptor.trade_mode,
                                "trade_mode_name": result.descriptor.trade_mode_name,
                                "tradable": result.descriptor.is_tradable,
                                "matched_by": result.reason.value,
                                "canonical_symbol": result.canonical_symbol,
                            }
                            for result in results
                        ],
                    }
                )
            )
            return 0
        print(
            f"# catalog_size={len(catalog)} "
            f"tradable={sum(1 for item in catalog if item.is_tradable)} "
            f"match_count={len(results)} query={search or '<all>'}"
        )
        print(describe_matches(results))
    return 0


def _collect(arguments: argparse.Namespace) -> int:
    settings = get_settings()
    profiles = arguments.broker_profile or ["default"]
    result = collect_historical_data(
        settings,
        profiles,
        arguments.symbol,
        DataType(arguments.data_type),
        arguments.timeframe
        or (settings.research.default_timeframe if arguments.data_type == "bar" else None),
        _parse_datetime(arguments.start),
        _parse_datetime(arguments.end),
        arguments.limit,
        arguments.parallel,
        arguments.max_workers,
    )
    print(_serializable(result))
    return 0


def _discover(arguments: argparse.Namespace) -> int:
    if arguments.input is not None:
        result = run_advanced_research(
            arguments.input,
            arguments.minimum_observations,
            arguments.regime_window,
            arguments.regime_low_quantile,
            arguments.regime_high_quantile,
            arguments.max_depth,
            arguments.training_fraction,
            arguments.ridge_alpha,
            arguments.rolling_beta_window,
            arguments.statistical_significance,
            arguments.output or get_settings().data.reports_directory,
        )
    else:
        if not arguments.symbol:
            raise ValueError("discover requires --input or at least one --symbol")
        symbols = [symbol for group in arguments.symbol for symbol in group]
        result = discover_relationships(symbols, arguments.minimum_observations)
    print(_serializable(result))
    return 0


def _research(arguments: argparse.Namespace) -> int:
    settings = get_settings()
    print(
        _serializable(
            run_historical_research(
                settings,
                arguments.broker_profile,
                arguments.relationship,
                arguments.timeframe,
                arguments.limit,
                arguments.rolling_beta_window or settings.research.rolling_beta_window,
                (
                    arguments.statistical_significance
                    if arguments.statistical_significance is not None
                    else settings.research.statistical_significance
                ),
            )
        )
    )
    return 0


def _backtest(arguments: argparse.Namespace) -> int:
    print(
        _serializable(
            run_no_lookahead_backtest(
                arguments.file,
                arguments.signal_column,
                arguments.gross_edge_column,
                arguments.cost_column,
                arguments.output or get_settings().data.reports_directory,
            )
        )
    )
    return 0


def _multi_backtest(arguments: argparse.Namespace) -> int:
    stages = build_signal_stages(
        arguments.stage_column,
        arguments.stage_weight,
        arguments.stage_threshold,
    )
    result = ResearchExperimentService().run_multi_stage(
        arguments.file,
        stages,
        arguments.gross_edge_column,
        arguments.cost_column,
        arguments.ensemble_threshold,
        arguments.output or get_settings().data.reports_directory,
    )
    print(_serializable(result))
    return 0


def _walk_forward(arguments: argparse.Namespace) -> int:
    config = WalkForwardConfig(
        train_observations=arguments.train_size,
        validation_observations=arguments.validation_size,
        test_observations=arguments.test_size,
        step_observations=arguments.step,
        thresholds=tuple(arguments.threshold or [0.0]),
        minimum_train_observations=arguments.minimum_train_observations,
    )
    result = ResearchExperimentService().run_walk_forward(
        arguments.file,
        arguments.signal_column,
        arguments.gross_edge_column,
        arguments.cost_column,
        config,
        arguments.output or get_settings().data.reports_directory,
    )
    print(_serializable(result))
    return 0


def _robustness(arguments: argparse.Namespace) -> int:
    config = MonteCarloConfig(
        simulations=arguments.simulations,
        confidence_level=arguments.confidence_level,
        random_seed=arguments.seed,
        block_size=arguments.block_size,
    )
    result = ResearchExperimentService().run_robustness(
        arguments.file,
        arguments.signal_column,
        arguments.gross_edge_column,
        arguments.cost_column,
        config,
        arguments.scenario or [],
        arguments.return_shock_std,
        arguments.output or get_settings().data.reports_directory,
    )
    print(_serializable(result))
    return 0


def _compare_brokers(arguments: argparse.Namespace) -> int:
    result = CrossBrokerExperimentService().run(
        arguments.source_a,
        arguments.source_b,
        arguments.broker_a,
        arguments.broker_b,
        arguments.symbol,
        ComparisonKind(arguments.kind),
        arguments.max_delay_ms,
        arguments.additional_cost,
        arguments.output or get_settings().data.reports_directory,
        arguments.contract_a,
        arguments.contract_b,
        SynchronizationMode(arguments.sync_mode),
        TickAggregation(arguments.tick_aggregation),
    )
    print(_serializable(result))
    return 0


def _symbol_specs(arguments: argparse.Namespace) -> int:
    settings = get_settings()
    profile, mapping = resolve_profile(settings, arguments.broker_profile)
    with MT5Adapter(profile) as adapter:
        available = adapter.symbols(visible_only=False)
        mapper = SymbolMapper(mapping)
        specifications = [
            adapter.contract_specification(
                mapper.resolve(symbol, available).broker_symbol
            ).to_dict()
            for symbol in arguments.symbol
        ]
    output = _serializable(specifications)
    print(output)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(output, encoding="utf-8")
    return 0


def _dashboard() -> int:
    import subprocess

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


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _serializable(value: Any) -> str:
    def convert(item: Any) -> Any:
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, (datetime, Path)):
            return str(item)
        if hasattr(item, "isoformat"):
            return item.isoformat()
        raise TypeError

    return json.dumps(value, default=convert, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
