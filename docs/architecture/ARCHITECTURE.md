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
- `validation` and `market_data`: data quality, symbol discovery, and time alignment
- `discovery`: formula generation and candidate-state filtering
- `backtesting`: deterministic cost-aware research metrics
- `infrastructure`: official MT5 integration and Parquet storage
- `application` and `cli`: diagnostics and commands
- `dashboard`: read-only research presentation

## Dependency direction

Domain and mathematical modules do not import MT5. The application layer constructs infrastructure adapters and passes normalized objects inward. This allows deterministic tests without a terminal and future non-MT5 data providers.

## Safety boundary

No execution interface exists. `MT5Adapter` validates the account mode during connection and disconnects if it is not demonstrably demo. Adding execution would require a future project decision, independent safety gates, audit records, and a separate package rather than an ad hoc adapter method.

## Extension points

A new broker should implement a provider contract returning normalized `Quote` and `Bar` objects. A new relationship should be declarative. A new cost component should be represented in `CostModel` and tested against both gross discrepancy and final net edge.

## Limitations

The initial graph is a formula catalog rather than a full currency graph. Cross-broker alignment, historical persistence, and contract-aware execution simulation are not yet complete.
