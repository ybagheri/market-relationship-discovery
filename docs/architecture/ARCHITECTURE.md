# Architecture

## Purpose

The platform separates data acquisition, relationship mathematics, statistical research, cost analysis, research execution, and presentation. MetaTrader 5 is an infrastructure adapter and never defines research formulas or account credentials.

## Layers

- `domain`: normalized immutable market objects and typed errors
- `config`: local, typed configuration loaded through Pydantic Settings
- `relationships`: expression parser, graph-ready definitions, and initial catalog
- `synthetic`: interval-aware formula evaluation from bid/ask quotes
- `costs`: gross-to-net edge calculations
- `statistics`: correlation, normalization, persistence, and lag research
- `validation` and `market_data`: quality, symbols, alignment, and cross-broker comparison
- `discovery`: formula generation and candidate-state filtering
- `backtesting`: next-observation execution, walk-forward, causal stages, and Monte Carlo robustness
- `infrastructure`: official MT5 integration and atomic Parquet/manifest storage
- `application`: diagnostics, profile resolution, collection, and research orchestration
- `cli`: argument parsing and command dispatch
- `dashboard`: read-only research presentation

## Dependency direction

Domain and mathematical modules do not import MT5. The application layer constructs infrastructure adapters and passes normalized objects inward. This allows deterministic tests without a terminal and future non-MT5 data providers.

## Safety boundary

No execution interface exists. `MT5Adapter` validates the account mode during connection and disconnects if it is not demonstrably demo. Adding execution would require a future project decision, independent safety gates, audit records, and a separate package rather than an ad hoc adapter method.

## Extension points

A new broker should implement a provider protocol returning normalized `Quote` and `Bar` objects. Broker profiles are selected from local configuration. A new relationship should be declarative. A new cost component should be represented in `CostModel` and tested against both gross discrepancy and final net edge.

## Limitations

The initial graph is a formula catalog rather than a full currency graph. Broker-A anchored synchronized comparison is implemented, but true parallel terminal processes, symmetric event-time synchronization, contract normalization, and execution simulation are not complete.
