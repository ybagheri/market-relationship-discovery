from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Protocol

from market_relationship_discovery.domain.errors import SymbolNotFoundError


@dataclass(frozen=True, slots=True)
class SymbolMatch:
    canonical_symbol: str
    broker_symbol: str
    strategy: str


class SymbolMapper:
    _search_aliases: ClassVar[dict[str, tuple[str, ...]]] = {
        "XAUUSD": ("gold", "xau"),
        "XAGUSD": ("silver", "xag"),
        "EURUSD": ("eurusd", "eur.usd", "eur/usd"),
        "GBPUSD": ("gbpusd", "gbp.usd", "gbp/usd"),
        "USDJPY": ("usdjpy", "usd.jpy", "usd/jpy"),
        "EURGBP": ("eurgbp", "eur.gbp", "eur/gbp"),
        "EURJPY": ("eurjpy", "eur.jpy", "eur/jpy"),
        "GBPJPY": ("gbpjpy", "gbp.jpy", "gbp/jpy"),
        "XAUEUR": ("xaueur", "xau.eur", "xau/eur", "gold.eur", "gold/eur"),
    }

    def __init__(self, configured: dict[str, str] | None = None) -> None:
        self._configured = configured or {}

    def resolve(self, canonical_symbol: str, available_symbols: list[str]) -> SymbolMatch:
        configured = self._configured.get(canonical_symbol)
        if configured and configured in available_symbols:
            return SymbolMatch(canonical_symbol, configured, "configuration")
        normalized = {self._normalize(symbol): symbol for symbol in available_symbols}
        direct = normalized.get(self._normalize(canonical_symbol))
        if direct:
            return SymbolMatch(canonical_symbol, direct, "normalized_name")
        for alias in self._search_aliases.get(canonical_symbol, (canonical_symbol.lower(),)):
            for normalized_name, broker_symbol in normalized.items():
                if self._normalize(alias) in normalized_name:
                    return SymbolMatch(canonical_symbol, broker_symbol, "alias")
        raise SymbolNotFoundError(
            f"No available symbol matched {canonical_symbol!r}; discover broker symbols first"
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())


class SymbolTradeMode(Enum):
    """Official MetaTrader 5 ``SYMBOL_TRADE_MODE_*`` values.

    A symbol with :attr:`DISABLED` is not tradable at the broker, so research
    results derived from it must not be presented as executable.
    """

    DISABLED = 0
    LONG_ONLY = 1
    SHORT_ONLY = 2
    CLOSE_ONLY = 3
    FULL = 4

    @classmethod
    def parse(cls, value: int | None) -> SymbolTradeMode | None:
        if value is None:
            return None
        try:
            return cls(value)
        except ValueError:
            return None


class MatchReason(Enum):
    """Why a broker symbol satisfied a discovery query."""

    EXACT_NAME = "exact_name"
    NAME = "name"
    DESCRIPTION = "description"
    ALIAS = "alias"


@dataclass(frozen=True, slots=True)
class SymbolDescriptor:
    """Broker-supplied metadata for one symbol.

    Mirrors the official MT5 ``symbol_info`` fields the platform relies on so
    that symbol discovery never has to assume a broker naming convention.
    """

    name: str
    description: str
    path: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    spread: int | None
    trade_mode: int | None
    visible: bool = False

    @property
    def trade_mode_name(self) -> str:
        mode = SymbolTradeMode.parse(self.trade_mode)
        return mode.name.lower() if mode is not None else "unknown"

    @property
    def is_tradable(self) -> bool:
        """Whether the broker permits trading this symbol at all.

        ``None`` trade modes are treated as not tradable so that missing metadata
        can never be interpreted as an executable opportunity.
        """
        mode = SymbolTradeMode.parse(self.trade_mode)
        return mode is not None and mode is not SymbolTradeMode.DISABLED

    @property
    def spread_in_points(self) -> int | None:
        return self.spread


class SymbolCatalogSource(Protocol):
    """Read-only provider of broker symbol metadata."""

    def symbol_details(self, visible_only: bool = ...) -> list[SymbolDescriptor]: ...


@dataclass(frozen=True, slots=True)
class SymbolSearchResult:
    """A broker symbol together with why it matched and its tradability."""

    descriptor: SymbolDescriptor
    reason: MatchReason
    canonical_symbol: str | None

    @property
    def name(self) -> str:
        return self.descriptor.name

    @property
    def is_tradable(self) -> bool:
        return self.descriptor.is_tradable


class SymbolSearchService:
    """Alias, name, and description aware broker symbol discovery.

    Brokers rarely name instruments the way a researcher does. Alpari, for
    example, exposes gold as ``XAUUSD`` described as ``Gold (Spot)`` rather
    than as ``GOLD`` or ``XAUUSD.a``. Searching by raw symbol name alone
    therefore hides valid instruments. This service matches a query against the
    symbol name, the broker-supplied description, and the canonical alias table
    used by :class:`SymbolMapper`, and reports which rule matched.
    """

    def __init__(self, source: SymbolCatalogSource) -> None:
        self._source = source

    def catalog(self, visible_only: bool = False) -> list[SymbolDescriptor]:
        return list(self._source.symbol_details(visible_only=visible_only))

    def search(
        self,
        query: str | None,
        visible_only: bool = False,
        tradable_only: bool = True,
    ) -> list[SymbolSearchResult]:
        """Return catalog entries matching ``query``.

        An empty or missing query lists the whole catalog, which matters because
        a broker can expose far more symbols than appear in the terminal watch
        window.

        ``tradable_only`` defaults to ``True`` so that a symbol the broker
        refuses to trade is never surfaced as a research candidate unless the
        caller explicitly asks for it.
        """
        catalog = self.catalog(visible_only=visible_only)
        if tradable_only:
            catalog = [descriptor for descriptor in catalog if descriptor.is_tradable]
        if query is None or not query.strip():
            return [
                SymbolSearchResult(descriptor, MatchReason.NAME, None) for descriptor in catalog
            ]
        results = [
            SymbolSearchResult(descriptor, reason, canonical)
            for descriptor in catalog
            for reason, canonical in self._match(descriptor, query)
        ]
        best: dict[str, SymbolSearchResult] = {}
        for result in results:
            current = best.get(result.name)
            if (
                current is None
                or self._REASON_PRIORITY[result.reason] < self._REASON_PRIORITY[current.reason]
            ):
                best[result.name] = result
        return sorted(best.values(), key=self._sort_key)

    def _match(
        self, descriptor: SymbolDescriptor, query: str
    ) -> list[tuple[MatchReason, str | None]]:
        normalized_query = SymbolMapper._normalize(query)
        normalized_name = SymbolMapper._normalize(descriptor.name)
        normalized_description = SymbolMapper._normalize(descriptor.description)
        matches: list[tuple[MatchReason, str | None]] = []
        if normalized_name == normalized_query:
            matches.append((MatchReason.EXACT_NAME, None))
        if normalized_query in normalized_name:
            matches.append((MatchReason.NAME, None))
        if normalized_query in normalized_description:
            matches.append((MatchReason.DESCRIPTION, None))
        for canonical, aliases in SymbolMapper._search_aliases.items():
            normalized_canonical = SymbolMapper._normalize(canonical)
            if normalized_canonical not in normalized_name:
                continue
            if any(normalized_query in SymbolMapper._normalize(alias) for alias in aliases):
                matches.append((MatchReason.ALIAS, canonical))
        return matches

    _REASON_PRIORITY: ClassVar[dict[MatchReason, int]] = {
        MatchReason.EXACT_NAME: 0,
        MatchReason.NAME: 1,
        MatchReason.ALIAS: 2,
        MatchReason.DESCRIPTION: 3,
    }

    @classmethod
    def _sort_key(cls, result: SymbolSearchResult) -> tuple[int, str]:
        return (cls._REASON_PRIORITY[result.reason], result.name.upper())

    def find_canonical(
        self,
        canonical_symbol: str,
        visible_only: bool = False,
    ) -> SymbolSearchResult | None:
        """Locate the broker symbol that implements a canonical research symbol."""
        catalog = {descriptor.name: descriptor for descriptor in self.catalog(visible_only)}
        mapper = SymbolMapper()
        try:
            match = mapper.resolve(canonical_symbol, list(catalog))
        except SymbolNotFoundError:
            return None
        descriptor = catalog[match.broker_symbol]
        return SymbolSearchResult(descriptor, MatchReason.ALIAS, canonical_symbol)


def describe_matches(results: Iterable[SymbolSearchResult]) -> str:
    """Render search results as stable, console-safe single lines.

    Broker descriptions can contain non-ASCII text, so the rendering replaces
    unencodable characters instead of raising on narrow console code pages.
    """
    lines: list[str] = []
    for result in results:
        descriptor = result.descriptor
        spread = "n/a" if descriptor.spread is None else str(descriptor.spread)
        canonical = result.canonical_symbol or "-"
        lines.append(
            f"{descriptor.name}\t{descriptor.currency_base}/{descriptor.currency_profit}"
            f"\tdigits={descriptor.digits}\tspread={spread}"
            f"\tmode={descriptor.trade_mode_name}\ttradable={descriptor.is_tradable}"
            f"\tmatched={result.reason.value}\tcanonical={canonical}"
            f"\tdescription={descriptor.description}"
        )
    return "\n".join(lines)


def available_names(descriptors: Sequence[SymbolDescriptor]) -> list[str]:
    return [descriptor.name for descriptor in descriptors]
