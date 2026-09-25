from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from types import ModuleType
from typing import Any

from market_relationship_discovery.config.settings import MT5Settings
from market_relationship_discovery.domain.errors import (
    DemoSafetyError,
    MT5ConnectionError,
    SymbolNotFoundError,
)
from market_relationship_discovery.domain.market import Bar, Quote


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    mode: str
    server: str
    currency: str
    leverage: int | None


@dataclass(frozen=True, slots=True)
class TerminalSnapshot:
    name: str
    company: str
    build: int
    path: str


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    name: str
    description: str
    path: str
    currency_base: str
    currency_profit: str
    digits: int
    point: float
    spread: int | None
    trade_mode: int | None


class MT5Adapter:
    def __init__(self, settings: MT5Settings) -> None:
        self._settings = settings
        self._module: ModuleType | None = None
        self._account: AccountSnapshot | None = None

    @property
    def is_connected(self) -> bool:
        return self._module is not None

    def connect(self) -> None:
        if self._settings.terminal_path is None:
            raise MT5ConnectionError("MT5 terminal path is not configured")
        if not self._settings.terminal_path.is_file():
            raise MT5ConnectionError(f"MT5 terminal does not exist: {self._settings.terminal_path}")
        module = import_module("MetaTrader5")
        arguments: dict[str, Any] = {
            "path": str(self._settings.terminal_path),
            "timeout": self._settings.timeout_seconds,
        }
        if self._settings.login is not None:
            arguments["login"] = self._settings.login
        if self._settings.server:
            arguments["server"] = self._settings.server
        if not module.initialize(**arguments):
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MetaTrader5 initialization failed: {error_code} {description}"
            )
        self._module = module
        try:
            self._account = self._read_account()
        except Exception:
            self.disconnect()
            raise

    def disconnect(self) -> None:
        if self._module is not None:
            self._module.shutdown()
        self._module = None
        self._account = None

    def __enter__(self) -> MT5Adapter:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    def terminal_info(self) -> TerminalSnapshot:
        module = self._required_module()
        value = module.terminal_info()
        if value is None:
            raise MT5ConnectionError("MT5 terminal information is unavailable")
        return TerminalSnapshot(
            name=str(value.name),
            company=str(value.company),
            build=int(value.build),
            path=str(value.path),
        )

    def account_info(self) -> AccountSnapshot:
        if self._account is None:
            self._account = self._read_account()
        return self._account

    def symbols(self, visible_only: bool = True) -> list[str]:
        module = self._required_module()
        values = module.symbols_get()
        if values is None:
            return []
        if visible_only:
            return [str(item.name) for item in values if bool(getattr(item, "visible", False))]
        return [str(item.name) for item in values]

    def symbol_info(self, symbol: str) -> SymbolInfo:
        module = self._required_module()
        value = module.symbol_info(symbol)
        if value is None:
            raise SymbolNotFoundError(f"MT5 symbol not found: {symbol}")
        return SymbolInfo(
            name=str(value.name),
            description=str(value.description),
            path=str(value.path),
            currency_base=str(value.currency_base),
            currency_profit=str(value.currency_profit),
            digits=int(value.digits),
            point=float(value.point),
            spread=int(value.spread) if value.spread is not None else None,
            trade_mode=int(value.trade_mode) if value.trade_mode is not None else None,
        )

    def select_symbol(self, symbol: str) -> bool:
        module = self._required_module()
        return bool(module.symbol_select(symbol, True))

    def current_quote(self, symbol: str) -> Quote:
        module = self._required_module()
        value = module.symbol_info_tick(symbol)
        if value is None:
            raise SymbolNotFoundError(f"MT5 returned no current tick for {symbol}")
        account = self.account_info()
        return Quote.create(
            timestamp=datetime.fromtimestamp(float(value.time), tz=UTC),
            broker=account.server,
            symbol=symbol,
            bid=float(value.bid),
            ask=float(value.ask),
            source="MetaTrader5",
            volume=int(value.volume) if value.volume else None,
            timestamp_offset_minutes=self._settings.source_utc_offset_minutes,
        )

    def ticks(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[Quote]:
        module = self._required_module()
        rows = module.copy_ticks_range(
            symbol,
            self._source_time(start),
            self._source_time(end),
            module.COPY_TICKS_ALL,
        )
        if rows is None:
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MT5 returned no ticks for {symbol}: {error_code} {description}"
            )
        return self._quotes_from_rows(rows, symbol)

    def recent_ticks(self, symbol: str, start: datetime, count: int) -> list[Quote]:
        if count < 1:
            raise ValueError("count must be positive")
        module = self._required_module()
        rows = module.copy_ticks_from(
            symbol,
            self._source_time(start),
            count,
            module.COPY_TICKS_ALL,
        )
        if rows is None:
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MT5 returned no recent ticks for {symbol}: {error_code} {description}"
            )
        return self._quotes_from_rows(rows, symbol)

    def _quotes_from_rows(self, rows: Any, symbol: str) -> list[Quote]:
        account = self.account_info()
        return [
            Quote.create(
                datetime.fromtimestamp(float(row["time"]), tz=UTC),
                account.server,
                symbol,
                float(row["bid"]),
                float(row["ask"]),
                "MetaTrader5",
                int(row["volume"]),
                timestamp_offset_minutes=self._settings.source_utc_offset_minutes,
            )
            for row in rows
        ]

    def bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        module = self._required_module()
        timeframe_value = self.timeframe(timeframe)
        rows = module.copy_rates_range(
            symbol,
            timeframe_value,
            self._source_time(start),
            self._source_time(end),
        )
        if rows is None:
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MT5 returned no bars for {symbol}: {error_code} {description}"
            )
        return self._bars_from_rows(rows, symbol, timeframe)

    def recent_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        if count < 1:
            raise ValueError("count must be positive")
        module = self._required_module()
        rows = module.copy_rates_from_pos(symbol, self.timeframe(timeframe), 0, count)
        if rows is None:
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MT5 returned no recent bars for {symbol}: {error_code} {description}"
            )
        return self._bars_from_rows(rows, symbol, timeframe)

    def _bars_from_rows(self, rows: Any, symbol: str, timeframe: str) -> list[Bar]:
        account = self.account_info()
        return [
            Bar.create(
                timestamp=datetime.fromtimestamp(float(row["time"]), tz=UTC),
                broker=account.server,
                symbol=symbol,
                timeframe=timeframe,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["tick_volume"]),
                source="MetaTrader5",
                timestamp_offset_minutes=self._settings.source_utc_offset_minutes,
            )
            for row in rows
        ]

    def timeframe(self, name: str) -> int:
        module = self._required_module()
        constants = {
            "M1": module.TIMEFRAME_M1,
            "M5": module.TIMEFRAME_M5,
            "M15": module.TIMEFRAME_M15,
            "M30": module.TIMEFRAME_M30,
            "H1": module.TIMEFRAME_H1,
            "H4": module.TIMEFRAME_H4,
            "D1": module.TIMEFRAME_D1,
        }
        try:
            return int(constants[name.upper()])
        except KeyError as exc:
            raise ValueError(f"unsupported timeframe: {name}") from exc

    def _read_account(self) -> AccountSnapshot:
        module = self._required_module()
        value = module.account_info()
        if value is None:
            error_code, description = module.last_error()
            raise MT5ConnectionError(
                f"MT5 account information is unavailable: {error_code} {description}"
            )
        demo_constant = getattr(module, "ACCOUNT_TRADE_MODE_DEMO", None)
        trade_mode = getattr(value, "trade_mode", None)
        if demo_constant is None or trade_mode is None or int(trade_mode) != int(demo_constant):
            mode = "UNKNOWN"
        else:
            mode = "DEMO"
        snapshot = AccountSnapshot(
            mode=mode,
            server=str(value.server),
            currency=str(value.currency),
            leverage=int(value.leverage) if value.leverage is not None else None,
        )
        if self._settings.demo_only and snapshot.mode != "DEMO":
            self.disconnect()
            raise DemoSafetyError(
                "Connected account is not demonstrably DEMO; research connection refused"
            )
        return snapshot

    def _source_time(self, timestamp: datetime) -> datetime:
        return timestamp - timedelta(minutes=self._settings.source_utc_offset_minutes)

    def _required_module(self) -> ModuleType:
        if self._module is None:
            raise MT5ConnectionError("MT5 adapter is not connected")
        return self._module
