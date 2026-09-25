🇮🇷 فارسی: [README فارسی](README.fa.md)

# Market Relationship Discovery

A Python quantitative research platform for discovering and validating market relationships, synthetic prices, pricing discrepancies, cross-broker differences, triangular relationships, lead/lag effects, and statistical-arbitrage candidates.

> **Research only:** this project does not guarantee arbitrage profits. The connected MT5 account must be demonstrably `DEMO`, and no order-execution implementation is included.

## Project status

Foundation through PnL-normalized multi-broker research phases implemented. The platform now includes two-terminal process-isolated collection, symmetric one-to-one event-time matching, explicit tick aggregation, contract-aware volume/PnL normalization, no-look-ahead research, walk-forward, and Monte Carlo robustness. Live execution remains disabled.

## Capabilities

- Read-only MetaTrader 5 data adapter for ticks, bars, symbols, account, and terminal metadata
- Explicit demo-account refusal before the connection is accepted
- UTC-normalized bid, ask, mid, and spread domain model
- Generic arithmetic formula engine for synthetic relationships
- Separation of theoretical and bid/ask-aware executable discrepancies
- Configurable spread-independent cost assumptions
- Pearson, Spearman, rolling z-score, half-life, and lead/lag analysis
- Data quality and timestamp-alignment utilities
- Multiple broker profiles with sequential read-only collection
- Parquet tick/bar datasets with reproducibility manifests
- Historical bar relationship research that never claims tick execution
- Next-observation backtesting that excludes same-timestamp edge leakage
- Walk-forward train/validation/test folds with train-only threshold selection
- Causal multi-stage signals, feature builders, and stage-level reporting
- Experiment IDs, source hashes, parameters, and JSON provenance reports
- Circular block-bootstrap Monte Carlo with reproducible random seeds
- Wider-spread, slippage, latency, and combined stress scenarios
- Nearest-timestamp cross-broker synchronization with explicit delay and unmatched counts
- Tick-only bid/ask crossable research after configurable additional cost
- Cross-broker opportunity frequency, duration, and two-source provenance
- Official MT5 contract metadata capture and JSON export
- Compatibility gate that blocks opportunities when contract normalization is required
- Process-isolated parallel collection with one worker process per broker profile
- Contract-aware volume and PnL normalization for cross-broker edges
- Symmetric mutual-nearest event-time matching with no duplicate quote reuse
- Explicit raw tick preservation and configurable timestamp aggregation
- Relationship catalog and candidate generation framework
- Streamlit research dashboard with a permanent demo/research warning

## Safety model

The current stage has no `order_send` or equivalent execution operation. A discrepancy is not called risk-free arbitrage unless the data timestamps, contract specifications, execution path, and costs support that conclusion. A mid-price difference alone is only a theoretical discrepancy.

Required configuration keeps `demo_only=true`. The adapter disconnects and raises an error if the MT5 account mode cannot be proven to be `DEMO`.

## Architecture

```text
CLI / Streamlit Dashboard
          |
 Research and Discovery
          |
 Statistics / Backtesting / Costs
          |
 Relationships and Synthetic Pricing
          |
 Validation and Market Data Alignment
          |
 MT5 Read-Only Adapter / Storage
```

See [architecture](docs/architecture/ARCHITECTURE.md) and [data flow](docs/architecture/DATA_FLOW.md).

## Installation

Python 3.12 or newer and Windows with MetaTrader 5 are recommended for live terminal integration.

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env`. Keep all terminal paths, local directories, and broker-specific symbol mappings in `.env`; never commit `.env` or credentials.

```dotenv
MT5__TERMINAL_PATH=C:\\path\\to\\terminal64.exe
MT5__DATA_PATH=C:\\path\\to\\terminal\\data
MT5__DEMO_ONLY=true
MT5__SOURCE_UTC_OFFSET_MINUTES=0
BROKERS={"DEMO":{"terminal_path":"C:\\\\path\\\\to\\\\demo\\\\terminal64.exe","demo_only":true}}
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

The research adapter deliberately rejects non-empty password configuration. MT5 authentication should be managed by the terminal, not application source. `source_utc_offset_minutes` defaults to zero and must only be changed after verifying a source clock offset; the original MT5 timestamp remains stored as `source_timestamp`.

## Quick start

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery mt5-info
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --symbol EURUSD GBPUSD
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery robustness examples\walk_forward_signals.csv --simulations 1000 --seed 42 --block-size 3
python -m market_relationship_discovery compare-brokers examples\broker_a_ticks.csv examples\broker_b_ticks.csv --broker-a BrokerA --broker-b BrokerB --symbol EURUSD --kind tick --max-delay-ms 100 --additional-cost 0.0001 --sync-mode symmetric --tick-aggregation last --contract-a examples\broker_a_contract.json --contract-b examples\broker_b_contract.json
```

The first relationship definitions include `EURGBP = EURUSD / GBPUSD`, `EURJPY = EURUSD * USDJPY`, `GBPJPY = GBPUSD * USDJPY`, `XAUEUR = XAUUSD / EURUSD`, and the Gold/Silver ratio.

## Dashboard

```bash
python -m market_relationship_discovery dashboard
```

The dashboard always displays `DEMO / RESEARCH MODE — NO LIVE TRADING`.

## Quality checks

```bash
pytest
ruff check .
black --check .
mypy
```

## Documentation

- [Persian README](README.fa.md)
- [MT5 setup](docs/mt5/SETUP.md)
- [Quickstart tutorial](docs/tutorials/QUICKSTART.md)
- [Research methodology](docs/research/METHODOLOGY.md)
- [Backtesting](docs/research/BACKTESTING.md)
- [Walk-forward validation](docs/research/WALK_FORWARD.md)
- [Monte Carlo robustness](docs/research/MONTE_CARLO.md)
- [Cross-broker comparison](docs/research/CROSS_BROKER.md)
- [Contract specifications](docs/research/CONTRACT_SPECIFICATION.md)
- [Parallel MT5 collection](docs/mt5/PARALLEL_COLLECTION.md)
- [PnL normalization](docs/research/PNL_NORMALIZATION.md)
- [Event-time synchronization](docs/research/EVENT_TIME.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Security policy](SECURITY.md)

## Limitations

Broker feeds and CFD construction can differ. Synthetic formulas can be mathematically valid but non-tradable. Bar data cannot establish tick-level arbitrage. Historical correlation, cointegration, or mean reversion does not guarantee a future edge. Costs, latency, slippage, sessions, and symbol specifications must be validated separately.

## License

A license has not yet been selected. No permission is granted to reuse this repository until a license is added by the project owner.
