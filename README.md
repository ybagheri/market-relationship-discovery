🇮🇷 فارسی: [README فارسی](README.fa.md)

# Market Relationship Discovery

A Python quantitative research platform for discovering and validating market relationships, synthetic prices, pricing discrepancies, cross-broker differences, triangular relationships, lead/lag effects, and statistical-arbitrage candidates.

> **Research only:** this project does not guarantee arbitrage profits. The connected MT5 account must be demonstrably `DEMO`, and no order-execution implementation is included.

## Project status

The research platform is feature-complete through the documented phases. Live
execution remains disabled and out of scope.

**Current work is measurement correctness, not new capability.** A full audit of
the pipeline found a class of defects that all behaved the same way: the code
produced a number that looked valid, carried it into a report, and let it be read
as evidence. A passing test suite did not catch any of them, because the tests
asserted that the pipeline produced a well-formed result, not that the result was
true. Version 1.9.0 corrects the ones that were found.

Every item in the audit's **High** list is now corrected, each with a regression
test that fails against the code as it was. Four since 1.9.0:

- `-` was an identifier character, so `A-B` was one symbol that cannot exist in a
  panel and the subtraction was discarded. A hyphenated broker name such as
  `XAU-USD` is now written quoted, because brokers do publish such names and
  removing the hyphen would have turned those into silent subtractions instead
- A broker that halved its `contract_size` without halving its `tick_value` was
  accepted as normalizable, so a normalized PnL was reported beside an otherwise
  crossable opportunity. No volume reconciles such a pair, so it is now refused
- The observation gate reported a candidate that had never been evaluated as one
  whose data had been measured and found too short
- `CostAwareAnalyzer` and `CostModel` had no caller and held a latency assumption
  they never applied; the single-symbol path claims no executable discrepancy, so
  they were removed rather than wired in

Corrected in 1.9.0, each with a regression test:

- Cross-broker alignment searched unsorted data, matching ticks to the wrong
  neighbours and silently discarding observations
- Opportunity episodes were grouped by row adjacency, so two separate instants
  were reported as one long, capturable opportunity
- The combined cross-broker edge was valued against both legs and summed,
  roughly doubling a symmetric opportunity
- `confidence_max_drawdown` read the wrong quantile and reported a bound milder
  than a typical drawdown
- Drawdown was measured without a zero seed, so a curve opening below its own
  high reported no drawdown
- Win rate was averaged over every bar rather than over the trades taken
- Walk-forward aggregates double-counted overlapping test windows
- The ridge ranker trained on statistics summarised over each candidate's whole
  series, contaminating the out-of-sample score
- The demo-only check was cached for the life of the adapter, so a terminal
  re-logged-in mid-session kept certifying itself
- A `DemoSafetyError` was reported as an ordinary connection failure
- Absent or malformed report fields were rendered as zero, which turned a parse
  failure into a statement about the market
- The Engle–Granger p-value used the zero-regressor distribution, so pairs
  whose residual is a near unit root were reported cointegrated, and that
  biased the false-discovery family built from the same number

The **High** list from that audit is now clear. The defects still open are the
**Medium** and **Low** items under **Open corrections** in
[the roadmap](docs/roadmap/ROADMAP.md), rather than left implicit, along with the
conventions each document states. Take them in the order the roadmap lists them.

Symbol discovery searches the whole broker catalog by name, description, and
alias, and reports which rule matched. Stationarity and cointegration use
`statsmodels` augmented Dickey-Fuller and KPSS tests, require at least 30 aligned
observations, and return an explicit reason instead of a result when the data
cannot support the test.

## Capabilities

- Read-only MetaTrader 5 data adapter for ticks, bars, symbols, account, and terminal metadata
- Explicit demo-account refusal before the connection is accepted
- The verified demo account mode is re-checked on a configurable TTL, because the terminal can be re-logged-in without restarting
- UTC-normalized bid, ask, mid, and spread domain model
- Generic arithmetic formula engine for synthetic relationships
- Separation of theoretical and bid/ask-aware executable discrepancies
- Configurable spread-independent cost assumptions, applied where the edge is computed
- Pearson, Spearman, rolling z-score, half-life, and lead/lag analysis
- Stationarity and cointegration diagnostics using `statsmodels` ADF and KPSS with explicit unavailable reasons
- Engle-Granger p-value adjusted for its cointegrating regressor, with the unadjusted value reported alongside
- Near-collinear pairs reported as unavailable rather than as a zero p-value
- Symbol discovery that matches broker name, broker description, and canonical alias
- Tradability-aware filtering so a non-tradable symbol is never surfaced as a candidate
- Data quality and timestamp-alignment utilities
- Multiple broker profiles with sequential read-only collection
- Parquet tick/bar datasets with reproducibility manifests
- Historical bar relationship research that never claims tick execution
- Next-observation backtesting that excludes same-timestamp edge leakage
- Walk-forward train/validation/test folds with train-only threshold selection, and overlapping test windows counted once
- Causal multi-stage signals, feature builders, and stage-level reporting
- Experiment IDs, source hashes, parameters, and JSON provenance reports
- Circular block-bootstrap Monte Carlo robustness with reproducible random seeds
- Drawdown measured from the starting equity, consistent between the backtester and the simulator
- Win rate and average return measured over the trades actually taken
- Wider-spread, slippage, latency, and combined stress scenarios that cannot improve on the baseline
- Nearest-timestamp cross-broker synchronization with explicit delay and unmatched counts
- Tick-only bid/ask crossable research after configurable additional cost
- Cross-broker opportunity frequency, duration, and two-source provenance
- Official MT5 contract metadata capture and JSON export
- Compatibility gate that refuses a pair whose contract size and tick value do not scale together, because no volume can reconcile them
- Process-isolated parallel collection with one worker process per broker profile
- Contract-aware volume and PnL normalization for cross-broker edges
- Margin model that treats a broker-reported zero as not reported, never free
- Fill feasibility against broker volume step and maximum, with partial-fill reporting
- A `volume_max`-capped leg blocks the cross-broker pair instead of passing the executable gate
- Measured round-trip latency from a supplied execution log, read without placing orders
- Overnight funding accrual including the triple-swap rollover
- Latency capture comparing measured opportunity duration against round-trip time
- Sensitivity sweep reporting how far a capture verdict travels from its assumption
- Execution feasibility verdict with separate blocking and advisory reasons
- Per-broker symbol labels so cross-broker research survives differing names
- Symmetric mutual-nearest event-time matching with no duplicate quote reuse, over chronologically verified data
- Event-time matching refuses unsorted input rather than pairing ticks with the wrong neighbour
- Opportunity episodes bounded by wall-clock continuity, with a configurable gap
- Explicit raw tick preservation and configurable timestamp aggregation
- Cross-broker edge valued once, with cross-leg disagreement reported rather than summed
- Relationship catalog and candidate generation framework
- Streamlit research dashboard with a permanent demo/research warning
- Interactive discrepancy and broker comparison charts from persisted experiment reports
- Causal low, normal, and high volatility regime detection
- Directed formula dependency-graph expansion with bounded depth
- Bar price-panel loading from wide or long CSV/Parquet
- Historical candidate evaluation with discrepancy, correlation, persistence, and regime metrics
- Deterministic chronological NumPy ridge ranking with out-of-sample RMSE, over causal features only
- False-discovery control across the discovered candidate family
- Candidate de-duplication by proven formula equivalence, with syntactic canonicalisation as fallback
- Cross-symbol coverage reporting and largest-shared-window analysis
- Contested flag when ADF and KPSS verdicts disagree
- Multi-broker dashboard with per-profile symbol resolution and health checks
- Discovery dashboard separating evaluated evidence from the declared catalog
- Rolling beta stability and retrospective cointegration/stationarity diagnostics
- Dashboard views render an absent, mistyped, or non-finite report field as unknown, never as a measured zero
- Dashboard reports a demo-safety refusal distinctly from a connection failure

## Safety model

The current stage has no `order_send` or equivalent execution operation. A discrepancy is not called risk-free arbitrage unless the data timestamps, contract specifications, execution path, and costs support that conclusion. A mid-price difference alone is only a theoretical discrepancy.

Required configuration keeps `demo_only=true`. The adapter disconnects and raises an error if the MT5 account mode cannot be proven to be `DEMO`.

That proof is a time-of-check, and the terminal is a separate long-lived process an operator can re-log-in to a different account without restarting. The account is therefore re-verified once `MT5__ACCOUNT_VERIFICATION_TTL_SECONDS` (default 300) has elapsed, so a session that changes account mid-run does not keep certifying itself, and every dataset manifest records the mode as it was at the time it was written. `is_connected` probes the terminal rather than testing for an imported handle, so a session closed elsewhere is not reported as connected. A failed terminal shutdown is logged rather than raised, because `disconnect` also runs on context exit and must not replace the result of the caller's work.

`DemoSafetyError` is reported distinctly from a connection failure in `doctor` and in the dashboard (`demo_safety_refused`). The refusal means the terminal connected and the account was not provably demo, which is the platform working as intended rather than a setup problem.

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
python -m market_relationship_discovery discover --input examples\prices.csv --regime-window 20 --rolling-beta-window 30 --statistical-significance 0.05 --max-depth 1 --training-fraction 0.7 --ridge-alpha 1.0 --output reports\research
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

## Defining a study once, for several brokers

Two brokers rarely name an instrument the same way, so a study is written with canonical research names and each profile maps them to whatever that broker publishes. The symbol list belongs in configuration, so two runs of the "same" study cannot describe different instruments:

```dotenv
SYMBOL_SETS__SETS={"metals":["XAUUSD","XAGUSD","XAUEUR"],
                   "energy":["WTI","BRENT","NGAS"],
                   "crypto":["BTCUSD","ETHUSD","XRPUSD"]}
```

Any command that takes symbols accepts `--symbol-set`, so a whole study is one argument across two or three brokers:

```bash
python -m market_relationship_discovery resolve-symbols --symbol-set energy --broker-profile ALPARI_1 --broker-profile ALPARI_2
python -m market_relationship_discovery collect --symbol-set energy --broker-profile ALPARI_1 --broker-profile ALPARI_2 --parallel --max-workers 2 --data-type bar --timeframe M1 --limit 500
python -m market_relationship_discovery symbol-specs --symbol-set metals --broker-profile ALPARI_1 --output config/specs/alpari1_metals.json
```

`resolve-symbols` reports how the set resolves on every profile without collecting anything, so a naming difference becomes a report rather than a collection failure part way through a run. On the observed demo pair the `energy` set resolves to `WTI`/`BRN`/`NG` on one broker and `WTI`/`BRENT`/`NGAS` on the other from the same research names. See [symbol mapping and broker naming](docs/mt5/SYMBOL_MAPPING.md).

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
- [Roadmap, with the open corrections still outstanding](docs/roadmap/ROADMAP.md)
- [Security policy](SECURITY.md)

## Limitations

Broker feeds and CFD construction can differ. Synthetic formulas can be mathematically valid but non-tradable. Bar data cannot establish tick-level arbitrage. Historical correlation, cointegration, or mean reversion does not guarantee a future edge. Costs, latency, slippage, sessions, and symbol specifications must be validated separately.

## License

A license has not yet been selected. No permission is granted to reuse this repository until a license is added by the project owner.
