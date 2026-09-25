class MarketRelationshipError(Exception):
    """Base exception for the platform."""


class ConfigurationError(MarketRelationshipError):
    """Raised when required configuration is absent or invalid."""


class InvalidFormulaError(MarketRelationshipError):
    """Raised when a synthetic formula cannot be parsed or evaluated."""


class InsufficientDataError(MarketRelationshipError):
    """Raised when a calculation does not have enough observations."""


class DemoSafetyError(MarketRelationshipError):
    """Raised when account mode violates the research-only safety policy."""


class MT5ConnectionError(MarketRelationshipError):
    """Raised when MetaTrader 5 cannot be initialized."""


class SymbolNotFoundError(MarketRelationshipError):
    """Raised when a configured symbol is unavailable."""


class DataQualityError(MarketRelationshipError):
    """Raised when market data violates required invariants."""
