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
- [x] Symbol discovery by name, description, and canonical alias
- [x] Tradability-aware filtering with disabled and unknown trade modes excluded
- [x] Whole-catalog discovery rather than only the terminal watch window
- [x] Tick and bar retrieval, including newest-tick selection on a closed market
- [x] Documented broker symbol mapping with an observed catalog

## Phase 2 — Market Data Layer

- [x] Normalized quote and bar objects
- [x] UTC enforcement
- [x] Data quality report
- [x] Timestamp alignment with tolerance
- [x] Parquet repository and atomic dataset manifests
- [x] Multiple broker profiles and sequential historical collection
- [x] Process-isolated parallel broker collection
- [x] Synchronized cross-broker comparison

## Phase 3 — Synthetic Pricing

- [x] Generic formula parser and engine
- [x] Bid/ask executable intervals
- [x] Initial relationship catalog

## Phase 4 — Discrepancy Engine

- [x] Theoretical and executable classification
- [x] Configurable cost-aware net edge
- [x] Tick bid/ask cross-broker discrepancy, delay, frequency, and duration
- [x] Contract specification capture and opportunity safety gate
- [x] PnL-normalized contract-aware research edge
- [x] Margin model that treats a broker-reported zero as not reported
- [x] Leverage-derived margin with explicit source labelling
- [x] Volume step and maximum fill feasibility with partial-fill reporting
- [x] Overnight funding accrual including the triple-swap rollover
- [x] Execution feasibility verdict integrated into the cross-broker summary
- [x] Per-broker symbol labels so cross-broker research survives differing names
- [ ] Reject, requote, and queue-position modelling

## Phase 5 — Statistical Research

- [x] Pearson and Spearman correlation
- [x] Rolling z-score
- [x] Half-life and lead/lag
- [x] Rolling beta and stability
- [x] Cointegration and stationarity tests using `statsmodels` ADF and KPSS
- [x] Explicit unavailable reasons for degenerate or too-short residual series
- [ ] Multiple-testing adjustment across discovered candidates

## Phase 6 — Discovery Engine

- [x] Candidate generation framework
- [x] Data-driven ranking and robustness filters

## Phase 7 — Backtesting

- [x] Basic deterministic cost-aware metrics
- [x] Next-observation signal execution without same-timestamp leakage
- [x] Walk-forward train/validation/test folds and train-only threshold selection
- [x] Causal multi-stage signal ensemble
- [x] Experiment IDs, source hashes, and JSON reports
- [x] Circular block-bootstrap Monte Carlo robustness
- [x] Wider-spread, slippage, latency, and combined stress scenarios

## Phase 8 — Dashboard

- [x] Persistent demo/research warning
- [x] Overview, monitor, catalog, and limitations views
- [x] Interactive discrepancy and broker charts

## Phase 9 — Advanced Research

- [x] Broker-A anchored synchronized cross-broker comparison and two-source provenance
- [x] Process-isolated parallel MT5 collection
- [x] Symmetric mutual-nearest event-time synchronization
- [x] Explicit tick duplicate aggregation and PnL normalization
- [x] Tick-level opportunity-duration analysis
- [x] Regime detection
- [x] Graph-based relationship discovery
- [x] Machine-learning-assisted ranking
- [x] Two live demo brokers verified independently through profile-aware diagnostics
- [x] Cross-broker studies across differing broker symbol names

## Phase 10 — Optional Execution

- [ ] Not implemented and explicitly out of scope
- [ ] If separately authorized later: demo-only, kill switch, exposure/loss limits, audit trail
