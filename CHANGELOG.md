# Changelog

All notable changes follow semantic versioning.

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
