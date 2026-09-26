# Changelog

All notable changes follow semantic versioning.

## [1.2.0] - 2026-09-26

### Added

- Margin model that treats a broker-reported `margin_initial` of `0.0` as *not reported* rather than free, with `broker_reported`, `leverage_derived`, and `unavailable` sources
- Fill feasibility that reduces requested volume to the broker `volume_step` and `volume_max`, reporting a partial fill instead of silently truncating
- Overnight funding accrual per night held, including the configurable triple-swap rollover weekday
- `ExecutionAssessor` combining margin and fill feasibility into a verdict with separate blocking and advisory reasons
- Execution feasibility reported in the cross-broker summary and experiment report, with a `_capital_unverified` classification suffix when margin cannot be determined
- `COSTS__` configuration for volume, leverage, funding, minimum fill ratio, and holding days
- `compare-brokers --volume`, `--leverage`, and `--minimum-fill-ratio`
- `compare-brokers --symbol-a` and `--symbol-b` for brokers that name an instrument differently
- `doctor --broker-profile` and `mt5-info --broker-profile` so every configured terminal is verifiable
- Bilingual execution and capital model documentation, including two live two-broker case studies

### Fixed

- `doctor` and `mt5-info` had no broker profile flag, so a second configured demo terminal could not be diagnosed at all
- `compare-brokers` required one symbol label for both feeds, which made cross-broker research impossible whenever broker names differ. The observed configuration publishes bitcoin as `BITCOIN` on one broker and `BTCUSD` on the other.
- `doctor` symbol discovery compared canonical names literally instead of resolving through the alias table

### Observed on two live demo brokers

- `Alpari-MT5-Demo` build 6184 leverage 500 and `AMarkets-Demo` build 6230 leverage 1000 are distinct brokers
- EURUSD contracts are compatible and produced zero crossable observations
- XAUUSD reports a ten times tick-value difference between brokers; the maximum normalized net PnL was +23.10 while the mean was -14.50
- BTCUSD is blocked by the contract gate because one broker quotes in whole dollars, so the apparent 5.98 price difference is mostly rounding rather than a dislocation

## [1.1.0] - 2026-09-26

### Fixed

- Stationarity diagnostics no longer report false-positive cointegration. The hand-rolled augmented Dickey-Fuller approximation inverted a near-singular OLS design matrix and returned a statistic of 3.7e16 with a zero p-value on real Alpari XAUEUR data, where a proper test gives ADF p=0.82 and KPSS p=0.01, both agreeing the residuals are not stationary.
- A constant residual series is reported as `unavailable` with a reason instead of returning a `-1e308` sentinel that was presented as strong cointegration evidence.
- Stationarity testing requires at least 30 aligned observations and reports `unavailable` below that.
- `recent_ticks` returns the newest ticks in the window. `copy_ticks_from` returns the oldest ticks at or after the requested time, so it silently collected stale data.
- Tick collection no longer fails outside trading hours. A search anchored at the current time returns an empty array rather than `None`, which was reported as no data.
- Blank optional configuration values such as `MT5__LOGIN=` load as "not configured" instead of failing validation, so the shipped example configuration works when copied verbatim.
- CLI output reconfigures the console to UTF-8 because broker symbol descriptions contain non-ASCII text that raised `UnicodeEncodeError` on narrow code pages.

### Added

- Alias, description, and name aware symbol discovery that reports which rule matched
- Tradability-aware filtering; a symbol with a disabled or unknown trade mode is excluded by default
- Whole-catalog search instead of only the terminal watch window, with `catalog_size` and `tradable` counts
- `symbols --visible-only`, `symbols --all`, and `symbols --json` output
- `MT5Adapter.symbol_details` reading full broker metadata in a single MT5 call
- `MT5__TICK_LOOKBACK_HOURS` and `MT5__TICK_MAX_LOOKBACK_HOURS` configuration with automatic window widening
- `kpss_p_value_is_bounded` and `unavailable_reason` fields on stationarity results
- `statsmodels` dependency replacing hand-rolled stationarity approximations
- Bilingual symbol mapping documentation with an observed broker catalog
- `.gitattributes` normalizing line endings

## [1.0.0] - 2026-09-25

### Added

- Rolling beta with warmup, sign consistency, and stability summaries
- OLS-residual cointegration proxy diagnostics
- Fixed-lag ADF and level KPSS approximation diagnostics
- Statistical results in historical and advanced candidate research reports
- Configurable rolling-beta and significance CLI/settings parameters
- Deterministic statistical tests and bilingual methodology documentation

## [0.9.0] - 2026-09-25

### Added

- Causal low, normal, and high volatility regime detection
- Directed relationship dependency hypergraph with bounded expansion
- Price-panel loader for wide and long CSV/Parquet inputs
- Historical candidate evaluation with correlation, discrepancy, persistence, and regime metrics
- Deterministic NumPy ridge ranking with chronological train/evaluation split
- `discover --input` advanced research workflow and provenance reports
- Bilingual advanced-discovery documentation and deterministic tests

## [0.8.0] - 2026-09-25

### Added

- Read-only report loader for persisted cross-broker experiment previews
- Interactive Plotly discrepancy charts with cost reference and crossable markers
- Interactive broker mid-price comparison charts
- Bilingual dashboard documentation
- Dashboard loader, chart, and safety tests

## [0.7.0] - 2026-09-25

### Added

- Contract-aware broker volume and PnL normalization
- Normalized opportunity and summary metrics
- One-to-one mutual-nearest symmetric event-time synchronization
- Signed delay and unmatched counts for both broker feeds
- Explicit tick aggregation policies for duplicate timestamp updates
- Bounded parallel worker retry for transient empty MT5 data
- Two configured demo terminals and live parallel tick collection
- PnL, volume, mutual-match, duplicate-policy, and synchronization tests
- Bilingual PnL and event-time documentation

## [0.6.0] - 2026-09-25

### Added

- Official MT5 contract specification capture and JSON export
- Currency, point, volume, trade-mode, contract-size, and tick-value compatibility analysis
- Cross-broker opportunity safety gate for incompatible or normalization-required contracts
- Process-isolated parallel collection with one worker per broker profile
- `symbol-specs` command and optional contract inputs for `compare-brokers`
- Bounded collection worker configuration and duplicate-profile protection
- Deterministic contract, blocked-opportunity, worker-planning, failure, and CLI tests
- Bilingual contract and parallel-collection documentation

## [0.5.0] - 2026-09-25

### Added

- Nearest-timestamp Broker-A anchored cross-broker synchronization
- Explicit signed delay, unmatched observation, and source preview metrics
- Bid, ask, mid, gross directional, and net cross-broker differences
- Crossable opportunity episodes with frequency and duration
- Theoretical-only bar comparison safety classification
- Two-source SHA-256 provenance in experiment manifests
- `compare-brokers` CLI for CSV and Parquet inputs
- Deterministic synchronization, cost, duration, bar-safety, and report tests
- Bilingual cross-broker comparison documentation

## [0.4.0] - 2026-09-25

### Added

- Circular block-bootstrap Monte Carlo trade-sequence resampling
- Common random numbers across stress scenarios
- Confidence quantiles, expected shortfall, probability positive, and drawdown distributions
- Wider-spread, slippage, latency, and combined stress presets
- Reproducible `robustness` CLI and `EXP-*` JSON reports
- Deterministic seed, stress, and distribution tests
- Bilingual Monte Carlo robustness documentation

## [0.3.0] - 2026-09-25

### Added

- Strict chronological walk-forward train/validation/test windows
- Train-only activation-threshold selection and fold-level metrics
- Causal rolling z-score, momentum, and volatility feature builders
- Weighted multi-stage signal ensemble with individual-stage reporting
- Experiment IDs, source SHA-256 hashes, parameters, and JSON provenance reports
- `multi-backtest` and `walk-forward` CLI commands
- Deterministic leakage, boundary, multi-stage, and report tests
- Bilingual walk-forward and backtesting documentation

## [0.2.0] - 2026-09-25

### Added

- Multiple typed broker profiles in local environment configuration
- Historical tick/bar collection with atomic Parquet storage and reproducibility manifests
- Explicit source UTC offset configuration with original `source_timestamp` preservation
- Bar-only historical relationship research
- `collect`, `discover`, `research`, and `backtest` CLI commands
- Next-observation backtesting and deterministic no-look-ahead tests
- Bilingual documentation for collection, timestamp quality, and backtesting

## [0.1.0] - 2026-09-25

### Added

- Python package and quality-tool configuration
- Typed local environment configuration
- UTC quote and bar domain models
- Demo-only read-only MetaTrader 5 adapter
- Environment doctor, terminal information, symbol search, and dashboard CLI
- Formula parser, synthetic pricing, discrepancy, and cost layers
- Basic statistical, discovery, validation, alignment, storage, and backtest components
- Unit and integration test foundations
- English and Persian README and architecture/setup/methodology documentation
