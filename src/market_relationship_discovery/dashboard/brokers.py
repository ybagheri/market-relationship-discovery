"""Multi-broker read-only views for the research dashboard.

The dashboard previously assumed a single terminal, which meant a second
configured broker was invisible and the market monitor requested quotes using
canonical research names such as ``XAUUSD`` rather than the broker's own label.
On the observed configuration that raised or silently missed the instrument,
because one broker publishes gold as ``XAUUSD`` and another as ``BITCOIN``.

This module resolves the same objects the CLI and collector already use:
:func:`resolve_profile` for profile selection and :class:`SymbolMapper` for
symbol resolution. Nothing here executes an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from market_relationship_discovery.application.commands import resolve_profile
from market_relationship_discovery.config.settings import MT5Settings, Settings
from market_relationship_discovery.domain.errors import (
    DemoSafetyError,
    MT5ConnectionError,
    SymbolNotFoundError,
)
from market_relationship_discovery.infrastructure.mt5.adapter import AccountSnapshot, MT5Adapter
from market_relationship_discovery.market_data.symbols import SymbolMapper

DEFAULT_PROFILE = "default"
MAX_MONITOR_SYMBOLS = 8


class ProfileStatus(StrEnum):
    CONNECTED_DEMO = "connected_demo"
    CONNECTED_UNKNOWN_MODE = "connected_unknown_mode"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class QuoteConnectable(Protocol):
    """Minimal read-only surface the dashboard needs from a broker terminal."""

    def __enter__(self) -> QuoteConnectable: ...

    def __exit__(self, *_: object) -> None: ...

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def account_info(self) -> AccountSnapshot: ...

    def terminal_info(self) -> object: ...

    def symbols(self, visible_only: bool = ...) -> list[str]: ...

    def current_quote(self, symbol: str) -> object: ...


@dataclass(frozen=True, slots=True)
class BrokerProfileRef:
    """A selectable broker profile without opening a connection."""

    name: str
    label: str
    terminal_path: str | None
    demo_only: bool
    is_default: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.name,
            "label": self.label,
            "terminal_path": self.terminal_path,
            "demo_only": self.demo_only,
            "is_default": self.is_default,
        }


@dataclass(frozen=True, slots=True)
class ProfileHealth:
    """Connection outcome for one profile, safe to render when it failed."""

    profile: str
    status: ProfileStatus
    detail: str
    server: str | None = None
    account_mode: str | None = None
    terminal: str | None = None
    tradable_symbols: int | None = None
    catalog_symbols: int | None = None

    @property
    def is_demo(self) -> bool:
        return self.status is ProfileStatus.CONNECTED_DEMO

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "status": self.status.value,
            "detail": self.detail,
            "server": self.server,
            "account_mode": self.account_mode,
            "terminal": self.terminal,
            "tradable_symbols": self.tradable_symbols,
            "catalog_symbols": self.catalog_symbols,
        }


@dataclass(frozen=True, slots=True)
class MonitorSymbol:
    """A canonical research symbol resolved to one broker's own label."""

    canonical: str
    broker_symbol: str
    strategy: str


def configured_profiles(settings: Settings) -> tuple[BrokerProfileRef, ...]:
    """List every selectable profile, default first then named profiles.

    The default profile is always offered so the dashboard keeps working with a
    configuration that has no ``BROKERS`` section at all.
    """
    references = [
        BrokerProfileRef(
            name=DEFAULT_PROFILE,
            label="default",
            terminal_path=_display(settings.mt5.terminal_path),
            demo_only=settings.mt5.demo_only,
            is_default=True,
        )
    ]
    for name in sorted(settings.brokers):
        profile = settings.brokers[name]
        references.append(
            BrokerProfileRef(
                name=name,
                label=name,
                terminal_path=_display(profile.terminal_path),
                demo_only=profile.demo_only,
                is_default=False,
            )
        )
    return tuple(references)


def profile_health(settings: Settings, profile_name: str) -> ProfileHealth:
    """Connect to one profile and report what it is, without raising.

    A dashboard must stay usable when one terminal is closed or missing, so a
    failure is reported as data rather than raised.
    """
    try:
        profile, _ = resolve_profile(settings, profile_name)
    except Exception as exc:
        return ProfileHealth(profile_name, ProfileStatus.FAILED, str(exc))
    if profile.terminal_path is None:
        return ProfileHealth(
            profile_name,
            ProfileStatus.NOT_CONFIGURED,
            "no terminal path is configured for this profile",
        )
    try:
        with MT5Adapter(profile) as adapter:
            account = adapter.account_info()
            terminal = adapter.terminal_info()
            catalog = adapter.symbol_details(visible_only=False)
            tradable = sum(1 for item in catalog if item.is_tradable)
            status = (
                ProfileStatus.CONNECTED_DEMO
                if account.mode == "DEMO"
                else ProfileStatus.CONNECTED_UNKNOWN_MODE
            )
            return ProfileHealth(
                profile=profile_name,
                status=status,
                detail=f"{getattr(terminal, 'name', 'terminal')} "
                f"build {getattr(terminal, 'build', '?')}",
                server=account.server,
                account_mode=account.mode,
                terminal=str(getattr(terminal, "name", "")),
                tradable_symbols=tradable,
                catalog_symbols=len(catalog),
            )
    except (MT5ConnectionError, DemoSafetyError, ValueError) as exc:
        return ProfileHealth(profile_name, ProfileStatus.FAILED, str(exc))
    except Exception as exc:
        return ProfileHealth(profile_name, ProfileStatus.FAILED, str(exc))


def resolve_monitor_symbols(
    profile: MT5Settings,
    shared_mapping: dict[str, str],
    available: list[str],
    limit: int = MAX_MONITOR_SYMBOLS,
) -> tuple[tuple[MonitorSymbol, ...], tuple[str, ...]]:
    """Resolve canonical symbols to broker labels, reporting what is missing.

    A per-profile mapping takes precedence over the shared one, matching the
    resolution order the collector uses. Symbols the broker does not offer are
    returned separately so the dashboard can say so instead of hiding them.
    """
    mapping = profile.symbol_mapping or shared_mapping
    mapper = SymbolMapper(mapping)
    resolved: list[MonitorSymbol] = []
    missing: list[str] = []
    for canonical in list(mapping)[:limit]:
        try:
            match = mapper.resolve(canonical, available)
        except SymbolNotFoundError:
            missing.append(canonical)
            continue
        resolved.append(
            MonitorSymbol(
                canonical=canonical,
                broker_symbol=match.broker_symbol,
                strategy=match.strategy,
            )
        )
    return tuple(resolved), tuple(missing)


def quote_rows(
    adapter: QuoteConnectable,
    symbols: tuple[MonitorSymbol, ...],
) -> list[dict[str, object]]:
    """Fetch one quote per resolved symbol.

    The previous implementation requested each quote three times to build one
    row, which triples broker round-trips and can mix values from different
    moments.
    """
    rows: list[dict[str, object]] = []
    for item in symbols:
        quote = adapter.current_quote(item.broker_symbol)
        rows.append(
            {
                "Canonical": item.canonical,
                "Broker Symbol": item.broker_symbol,
                "Bid": getattr(quote, "bid", None),
                "Ask": getattr(quote, "ask", None),
                "Mid": getattr(quote, "mid", None),
                "Spread": getattr(quote, "spread", None),
                "Timestamp (UTC)": getattr(quote, "timestamp", None),
            }
        )
    return rows


def monitor_symbols(
    settings: Settings,
    profile_name: str,
    adapter: QuoteConnectable,
    limit: int = MAX_MONITOR_SYMBOLS,
) -> tuple[tuple[MonitorSymbol, ...], tuple[str, ...]]:
    """Resolve the monitor's symbols against a live broker catalog."""
    profile, shared_mapping = resolve_profile(settings, profile_name)
    available = adapter.symbols(visible_only=False)
    return resolve_monitor_symbols(profile, shared_mapping, available, limit)


def _display(path: object) -> str | None:
    return str(path) if path is not None else None
