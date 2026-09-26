🇮🇷 فارسی: [README فارسی](README.fa.md)

# Market Relationship Discovery

A Python quantitative research platform for discovering and validating market relationships, synthetic prices, pricing discrepancies, cross-broker differences, triangular relationships, lead/lag effects, and statistical-arbitrage candidates.

> **Research only:** this project does not guarantee arbitrage profits. The connected MT5 account must be demonstrably `DEMO`, and no order-execution implementation is included.

## Project status

Foundation through advanced deterministic research phases implemented. The platform now includes causal volatility regimes, formula dependency-graph discovery, bar-panel candidate evaluation, chronological NumPy ridge ranking, two-terminal process-isolated collection, symmetric event-time matching, contract-aware PnL normalization, walk-forward, and Monte Carlo robustness. Live execution remains disabled.

Symbol discovery searches the whole broker catalog by name, description, and alias, and reports which rule matched. Stationarity and cointegration use `statsmodels` augmented Dickey-Fuller and KPSS tests, require at least 30 aligned observations, and return an explicit reason instead of a result when the data cannot support the test.

## Capabilities

- Read-only MetaTrader 5 data adapter for ticks, bars, symbols, account, and terminal metadata
- Explicit demo-account refusal before the connection is accepted
- UTC-normalized bid, ask, mid, and spread domain model
- Generic arithmetic formula engine for synthetic relationships
- Separation of theoretical and bid/ask-aware executable discrepancies
- Configurable spread-independent cost assumptions
- Pearson, Spearman, rolling z-score, half-life, and lead/lag analysis
- Stationarity and cointegration diagnostics using `statsmodels` ADF and KPSS with explicit unavailable reasons
- Symbol discovery that matches broker name, broker description, and canonical alias
- Tradability-aware filtering so a non-tradable symbol is never surfaced as a candidate
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
- Margin model that treats a broker-reported zero as not reported, never free
- Fill feasibility against broker volume step and maximum, with partial-fill reporting
- Overnight funding accrual including the triple-swap rollover
- Execution feasibility verdict with separate blocking and advisory reasons
- Per-broker symbol labels so cross-broker research survives differing names
- Symmetric mutual-nearest event-time matching with no duplicate quote reuse
- Explicit raw tick preservation and configurable timestamp aggregation
- Relationship catalog and candidate generation framework
- Streamlit research dashboard with a permanent demo/research warning
- Interactive discrepancy and broker comparison charts from persisted experiment reports
- Causal low, normal, and high volatility regime detection
- Directed formula dependency-graph expansion with bounded depth
- Bar price-panel loading from wide or long CSV/Parquet
- Historical candidate evaluation with discrepancy, correlation, persistence, and regime metrics
- Deterministic chronological NumPy ridge ranking with out-of-sample RMSE
- False-discovery control across the discovered candidate family
- Candidate de-duplication by canonical formula before testing
- Cross-symbol coverage reporting and largest-shared-window analysis
- Contested flag when ADF and KPSS verdicts disagree
- Multi-broker dashboard with per-profile symbol resolution and health checks
- Rolling beta stability and retrospective cointegration/stationarity diagnostics

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
MT5__TICK_LOOKBACK_HOURS=24
MT5__TICK_MAX_LOOKBACK_HOURS=168
BROKERS={"DEMO":{"terminal_path":"C:\\\\path\\\\to\\\\demo\\\\terminal64.exe","demo_only":true}}
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

Blank optional values such as `MT5__LOGIN=` mean "not configured" rather than a validation failure. The research adapter deliberately rejects non-empty password configuration. MT5 authentication should be managed by the terminal, not application source. `source_utc_offset_minutes` defaults to zero and must only be changed after verifying a source clock offset; the original MT5 timestamp remains stored as `source_timestamp`.

Tick requests search backwards from the current time and widen the window while too few ticks are available, because the newest tick can be hours behind the clock outside trading hours. `MT5__TICK_LOOKBACK_HOURS` sets the initial window and `MT5__TICK_MAX_LOOKBACK_HOURS` caps it.

## Quick start

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery doctor --broker-profile ALPARI_2
python -m market_relationship_discovery mt5-info --broker-profile ALPARI_2
python -m market_relationship_discovery symbols --search gold
python -m market_relationship_discovery symbols --search silver --json
python -m market_relationship_discovery symbols --all
python -m market_relationship_discovery collect --broker-profile DEMO --symbol XAUUSD --symbol EURUSD --symbol XAUEUR --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery collect --symbol XAUUSD --data-type tick --limit 500
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile BROKER_A --broker-profile BROKER_B --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery symbol-specs --broker-profile DEMO --symbol EURUSD --output config/specs/demo_eurusd.json
python -m market_relationship_discovery research --broker-profile DEMO --relationship XAUEUR_SYNTHETIC --limit 500
python -m market_relationship_discovery discover --input data\prices.csv --regime-window 20 --rolling-beta-window 30 --statistical-significance 0.05 --max-depth 1 --training-fraction 0.7 --ridge-alpha 1.0 --output reports\research
python -m market_relationship_discovery backtest examples\no_lookahead_signals.csv
python -m market_relationship_discovery multi-backtest examples\walk_forward_signals.csv --stage-column momentum_score --stage-column confirmation_score --stage-weight 0.5 --stage-weight 0.5
python -m market_relationship_discovery walk-forward examples\walk_forward_signals.csv --train-size 12 --validation-size 8 --test-size 8 --step 8 --threshold 0 --threshold 0.5 --threshold 0.9
python -m market_relationship_discovery robustness examples\walk_forward_signals.csv --simulations 1000 --seed 42 --block-size 3
python -m market_relationship_discovery compare-brokers examples\broker_a_ticks.csv examples\broker_b_ticks.csv --broker-a BrokerA --broker-b BrokerB --symbol EURUSD --kind tick --max-delay-ms 100 --additional-cost 0.0001 --sync-mode symmetric --tick-aggregation last --contract-a examples\broker_a_contract.json --contract-b examples\broker_b_contract.json
```

The first relationship definitions include `EURGBP = EURUSD / GBPUSD`, `EURJPY = EURUSD * USDJPY`, `GBPJPY = GBPUSD * USDJPY`, `XAUEUR = XAUUSD / EURUSD`, and the Gold/Silver ratio.

## Multiple brokers

Each configured broker is an independent, demo-only profile with its own symbol mapping. Diagnose them separately, because a passing check on one profile says nothing about another:

```bash
python -m market_relationship_discovery doctor --broker-profile ALPARI_1
python -m market_relationship_discovery doctor --broker-profile ALPARI_2
python -m market_relationship_discovery collect --parallel --max-workers 2 --broker-profile ALPARI_1 --broker-profile ALPARI_2 --symbol EURUSD --data-type tick --limit 500
python -m market_relationship_discovery compare-brokers a.parquet b.parquet --broker-a Alpari-MT5-Demo --broker-b AMarkets-Demo --symbol BTCUSD --symbol-a BITCOIN --symbol-b BTCUSD --contract-a specs/a.json --contract-b specs/b.json --volume 1.0 --leverage 500
```

Brokers rarely name an instrument identically, and a shared ticker does not imply a shared contract. Two demo brokers observed on 2026-09-26 publish bitcoin as `BITCOIN` and `BTCUSD`, quote gold with a ten times tick-value difference, and price bitcoin to the cent on one side and to whole dollars on the other. The contract gate blocks that comparison rather than reporting a false opportunity. See [execution and capital model](docs/research/EXECUTION_MODEL.md).

## Dashboard

```bash
python -m market_relationship_discovery dashboard
```

The dashboard always displays `DEMO / RESEARCH MODE — NO LIVE TRADING`. It includes read-only interactive charts for discrepancy metrics and aligned broker mid prices, using persisted `EXP-*.json` reports from `DATA__REPORTS_DIRECTORY`. The report preview contains at most 20 aligned observations; rerun `compare-brokers` to refresh it.

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
- [Symbol mapping and broker naming](docs/mt5/SYMBOL_MAPPING.md)
- [Quickstart tutorial](docs/tutorials/QUICKSTART.md)
- [Research methodology](docs/research/METHODOLOGY.md)
- [Backtesting](docs/research/BACKTESTING.md)
- [Walk-forward validation](docs/research/WALK_FORWARD.md)
- [Monte Carlo robustness](docs/research/MONTE_CARLO.md)
- [Cross-broker comparison](docs/research/CROSS_BROKER.md)
- [Contract specifications](docs/research/CONTRACT_SPECIFICATION.md)
- [Execution and capital model](docs/research/EXECUTION_MODEL.md)
- [Multiple testing and discovery](docs/research/MULTIPLE_TESTING.md)
- [Panel coverage and candidate families](docs/research/PANEL_COVERAGE.md)
- [Parallel MT5 collection](docs/mt5/PARALLEL_COLLECTION.md)
- [PnL normalization](docs/research/PNL_NORMALIZATION.md)
- [Event-time synchronization](docs/research/EVENT_TIME.md)
- [Dashboard](docs/dashboard/DASHBOARD.md)
- [Advanced discovery](docs/research/ADVANCED_DISCOVERY.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Security policy](SECURITY.md)

## Limitations

Broker feeds and CFD construction can differ. Synthetic formulas can be mathematically valid but non-tradable. Bar data cannot establish tick-level arbitrage. Historical correlation, cointegration, or mean reversion does not guarantee a future edge. Costs, latency, slippage, sessions, and symbol specifications must be validated separately.

## License

A license has not yet been selected. No permission is granted to reuse this repository until a license is added by the project owner.
