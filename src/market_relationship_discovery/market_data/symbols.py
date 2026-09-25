import re
from dataclasses import dataclass
from typing import ClassVar

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
