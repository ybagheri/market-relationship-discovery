from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from market_relationship_discovery.costs.execution import DEFAULT_MINIMUM_FILL_RATIO
from market_relationship_discovery.domain.errors import MarketRelationshipError


class MT5Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    terminal_path: Path | None = None
    data_path: Path | None = None
    demo_only: bool = True
    login: int | None = None
    password: str = ""
    server: str = ""
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    source_utc_offset_minutes: int = Field(default=0, ge=-1440, le=1440)
    tick_lookback_hours: int = Field(default=24, ge=1, le=8760)
    tick_max_lookback_hours: int = Field(default=168, ge=1, le=8760)
    symbol_mapping: dict[str, str] = Field(default_factory=dict)
    # How long a verified DEMO account mode stays trusted. The terminal is a
    # separate process an operator can re-log-in without restarting, so the
    # guarantee is re-checked rather than cached for the life of the adapter.
    account_verification_ttl_seconds: int = Field(default=300, ge=1, le=86400)

    @field_validator("login", mode="before")
    @classmethod
    def blank_login_is_absent(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("terminal_path", "data_path", mode="before")
    @classmethod
    def blank_path_is_absent(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("server", mode="before")
    @classmethod
    def blank_server_is_absent(cls, value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str) and not value.strip():
            return ""
        return value

    @field_validator("password", mode="before")
    @classmethod
    def blank_password_is_absent(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    @field_validator("password")
    @classmethod
    def reject_nonempty_password(cls, value: str) -> str:
        if value:
            raise ValueError("Passwords are not supported in the research configuration")
        return value

    @model_validator(mode="after")
    def check_tick_lookback_order(self) -> "MT5Settings":
        if self.tick_max_lookback_hours < self.tick_lookback_hours:
            raise ValueError("tick_max_lookback_hours must be at least tick_lookback_hours")
        return self


class DataSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timezone: str = "UTC"
    max_alignment_delay_ms: int = Field(default=100, ge=0)
    cache_enabled: bool = True
    raw_directory: Path = Path("data/raw")
    processed_directory: Path = Path("data/processed")
    cache_directory: Path = Path("data/cache")
    reports_directory: Path = Path("reports/research")
    collection_max_workers: int = Field(default=2, ge=1, le=8)
    collection_attempts: int = Field(default=3, ge=1, le=5)


class ResearchSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_timeframe: str = "M1"
    minimum_observations: int = Field(default=100, ge=2)
    zscore_window: int = Field(default=100, ge=2)
    rolling_beta_window: int = Field(default=30, ge=2)
    statistical_significance: float = Field(default=0.05, gt=0.0, lt=1.0)
    # A named set of research symbols to study, so a run does not have to repeat
    # every symbol on the command line. The names are canonical research symbols,
    # not broker names: `SYMBOL_MAPPING` translates them per broker, because two
    # brokers rarely publish an instrument the same way.
    symbol_set: str | None = None


class SymbolSetSettings(BaseModel):
    """Named symbol sets, each a list of canonical research symbols.

    Brokers publish different names for the same instrument, so a symbol to
    research is a research-level name and the broker name is resolved per
    profile. A set is defined once here and referenced by name, so the same
    research question can be run across two or three brokers without repeating
    the list or risking the two runs describing different instruments.
    """

    model_config = ConfigDict(extra="ignore")

    default: list[str] = Field(default_factory=list)
    sets: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_names(self) -> "SymbolSetSettings":
        if self.default and "default" in self.sets:
            raise ValueError(
                "define the default symbol set as SYMBOL_SETS__DEFAULT, not as an entry "
                "named 'default' in SYMBOL_SETS__SETS"
            )
        for name, symbols in self.sets.items():
            if not name.strip():
                raise ValueError("a symbol set name cannot be blank")
            if not symbols:
                raise ValueError(f"symbol set {name!r} is empty")
        return self

    def resolve(self, name: str | None) -> tuple[str, list[str]]:
        """Return the set name and its symbols.

        A name that is not configured raises rather than falling back, because a
        silent fallback would run a study on symbols the caller did not ask for
        and report a result about the wrong instruments.
        """
        if name is None:
            available = sorted(self.sets) or ["(the configured default)"]
            raise MarketRelationshipError(
                "no symbol set selected; pass --symbol-set, or configure one. "
                f"Available: {available}"
            )
        if name == "default":
            symbols = list(self.default)
            if not symbols:
                raise MarketRelationshipError(
                    "the default symbol set is empty; set SYMBOL_SETS__DEFAULT or "
                    "name a set explicitly"
                )
            return name, symbols
        if name not in self.sets:
            available = sorted(self.sets)
            raise MarketRelationshipError(
                f"Unknown symbol set {name!r}; configured: {available or ['(none)']}"
            )
        return name, list(self.sets[name])


class CostSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    commission: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    latency_assumption_ms: int = Field(default=50, gt=0)
    latency_log_path: Path | None = None
    latency_log_statistic: str = "median"
    other_costs: float = Field(default=0.0, ge=0)
    volume: float = Field(default=1.0, gt=0)
    leverage: int | None = Field(default=None, gt=0)
    funding_enabled: bool = True
    funding_daily_rate: float = Field(default=0.0, ge=0)
    minimum_fill_ratio: float = Field(default=DEFAULT_MINIMUM_FILL_RATIO, ge=0.0, le=1.0)
    minimum_capturable_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    adverse_move_allowance: float = Field(default=0.0, ge=0)
    holding_days: int = Field(default=1, ge=0, le=365)


class DashboardSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8501, ge=1, le=65535)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    mt5: MT5Settings = Field(default_factory=MT5Settings)
    brokers: dict[str, MT5Settings] = Field(default_factory=dict)
    data: DataSettings = Field(default_factory=DataSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    symbol_sets: SymbolSetSettings = Field(default_factory=SymbolSetSettings)
    costs: CostSettings = Field(default_factory=CostSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    symbol_mapping: dict[str, str] = Field(default_factory=dict)
