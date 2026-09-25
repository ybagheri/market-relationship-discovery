# Changelog

All notable changes follow semantic versioning.

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
