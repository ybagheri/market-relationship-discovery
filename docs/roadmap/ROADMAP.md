# Roadmap

Status: `[ ] Planned`, `[~] In progress`, `[x] Completed`.

## Phase 0 — Foundation

- [x] Audit the initially empty repository
- [x] Establish package, typed configuration, and logging
- [x] Establish deterministic test suite
- [x] Create English and Persian documentation

## Phase 1 — MT5 Connectivity

- [x] Read-only official MT5 adapter
- [x] Terminal and account health diagnostics
- [x] Demo-only account validation
- [x] Symbol discovery and metadata
- [x] Tick and bar retrieval

## Phase 2 — Market Data Layer

- [x] Normalized quote and bar objects
- [x] UTC enforcement
- [x] Data quality report
- [x] Timestamp alignment with tolerance
- [x] Parquet repository and atomic dataset manifests
- [x] Multiple broker profiles and sequential historical collection
- [ ] Synchronized parallel multi-broker comparison

## Phase 3 — Synthetic Pricing

- [x] Generic formula parser and engine
- [x] Bid/ask executable intervals
- [x] Initial relationship catalog

## Phase 4 — Discrepancy Engine

- [x] Theoretical and executable classification
- [x] Configurable cost-aware net edge
- [~] Contract-aware cross-broker discrepancy engine

## Phase 5 — Statistical Research

- [x] Pearson and Spearman correlation
- [x] Rolling z-score
- [x] Half-life and lead/lag
- [ ] Rolling beta and stability
- [ ] Cointegration and stationarity tests

## Phase 6 — Discovery Engine

- [x] Candidate generation framework
- [ ] Data-driven ranking and robustness filters

## Phase 7 — Backtesting

- [x] Basic deterministic cost-aware metrics
- [x] Next-observation signal execution without same-timestamp leakage
- [ ] Walk-forward validation
- [ ] Monte Carlo robustness

## Phase 8 — Dashboard

- [x] Persistent demo/research warning
- [x] Overview, monitor, catalog, and limitations views
- [ ] Interactive discrepancy and broker charts

## Phase 9 — Advanced Research

- [ ] Multi-broker synchronized datasets
- [ ] Tick-level opportunity-duration analysis
- [ ] Regime detection
- [ ] Graph-based relationship discovery
- [ ] Machine-learning-assisted ranking

## Phase 10 — Optional Execution

- [ ] Not implemented and explicitly out of scope
- [ ] If separately authorized later: demo-only, kill switch, exposure/loss limits, audit trail
