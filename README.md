🇮🇷 فارسی: [README فارسی](README.fa.md)

# Market Relationship Discovery

A Python quantitative research platform for discovering and validating market relationships, synthetic prices, pricing discrepancies, cross-broker differences, triangular relationships, lead/lag effects, and statistical-arbitrage candidates.

> **Research only:** this project does not guarantee arbitrage profits. The connected MT5 account must be demonstrably `DEMO`, and no order-execution implementation is included.

## Project status

Initial foundation implemented. MT5 connectivity, demo verification, normalized quotes, a formula-based synthetic pricing engine, discrepancy and cost layers, basic statistics, tests, CLI diagnostics, and a dashboard foundation are available. Advanced backtesting and multi-broker ingestion remain in progress.

## Capabilities

- Read-only MetaTrader 5 data adapter for ticks, bars, symbols, account, and terminal metadata
- Explicit demo-account refusal before the connection is accepted
- UTC-normalized bid, ask, mid, and spread domain model
- Generic arithmetic formula engine for synthetic relationships
- Separation of theoretical and bid/ask-aware executable discrepancies
- Configurable spread-independent cost assumptions
- Pearson, Spearman, rolling z-score, half-life, and lead/lag analysis
- Data quality and timestamp-alignment utilities
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
DATA__TIMEZONE=UTC
DATA__MAX_ALIGNMENT_DELAY_MS=100
```

The research adapter deliberately rejects non-empty password configuration. MT5 authentication should be managed by the terminal, not application source.

## Quick start

```bash
python -m market_relationship_discovery doctor
python -m market_relationship_discovery mt5-info
python -m market_relationship_discovery symbols --search gold
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
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Security policy](SECURITY.md)

## Limitations

Broker feeds and CFD construction can differ. Synthetic formulas can be mathematically valid but non-tradable. Bar data cannot establish tick-level arbitrage. Historical correlation, cointegration, or mean reversion does not guarantee a future edge. Costs, latency, slippage, sessions, and symbol specifications must be validated separately.

## License

A license has not yet been selected. No permission is granted to reuse this repository until a license is added by the project owner.
