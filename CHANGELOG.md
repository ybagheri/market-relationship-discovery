# Changelog

All notable changes follow semantic versioning.

## [1.7.0] - 2026-09-26

### Added

- Latency sensitivity sweep reporting how far a capture verdict travels from its configured baseline
- Fragility classification: `always_holds`, `stable`, `sensitive`, `knife_edge`, `nominal`, and `always_fails`
- A `nominal` class for verdicts that survive arithmetically while capturing almost nothing, with baseline capturable fraction and captured share reported alongside
- Adverse-move sweep against a fixed round trip
- Episodes rebuilt from a persisted capture report, so a sweep needs no recollection or re-alignment
- `compare-brokers --latency-grid-ms`, recorded in the provenance manifest
- Sensitivity panel in the dashboard with a distinct warning per fragility class
- Bilingual sensitivity documentation

### Observed

- XAUUSD classified `nominal` and fragile: the binary verdict holds from a 2 ms to a 2000 ms round trip, but only 2 of 16 episodes are capturable and the captured share of the edge falls from 14.6 percent to 0.6 percent while the binary answer never changes
- BTCUSD classified `always_holds` and not fragile: 7 of 10 episodes remain capturable at a 20-second round trip, with 70.8 percent of the peak edge surviving

### Fixed

- The first sweep run classified the gold comparison as `stable`, which a binary survives check reports whenever any episode is capturable at every grid point. That is arithmetic stability presented as a result, and the classifier now judges materiality before stability.

## [1.6.1] - 2026-09-26

### Fixed

- A zero round trip reported every measured episode as fully capturable, which is the most flattering answer the model can produce and exactly what an unset configuration value silently yields. `latency_per_leg_ms` must now be positive, and `COSTS__LATENCY_ASSUMPTION_MS` defaults to 50. An absent latency assumption is unknown, not free, the same way a broker-reported margin of zero is unknown rather than free margin.

### Observed on live bitcoin

- 800 live ticks from each demo broker while both feeds were active within five seconds of each other
- With contract specifications: `blocked_by_contract_specification`, 287 of 296 aligned observations blocked, zero opportunities
- Maximum gross edge was $17.00 on an $84,000 asset with zero spread on both feeds, about two basis points
- The cross-broker difference of $5.84 mean absolute exceeded broker A's own $3.68 mean tick-to-tick move, so the feeds do not track each other closely enough for the edge to mean anything
- The difference is not one-way: 62 percent below against 35 percent above, mean −$2.89 with a standard deviation of $6.85
- Without contract specifications the same data yields 97 percent crossable and a mean captured edge of 91 percent of peak, labelled `crossable_research_contract_unverified_capital_unverified`
- Latency separates the regimes: gold's median episode was 0 ms with 2 of 16 capturable, while bitcoin's median episode was 65.5 seconds with 8 of 10 capturable

## [1.6.0] - 2026-09-26

### Added

- Latency capture model comparing each measured opportunity episode against the time a round trip takes
- Capturable fraction under a stated linear decay assumption, with capturable, marginal, and not-capturable verdicts
- `_not_capturable_within_latency` classification suffix when no episode outlasts the round trip
- `compare-brokers --latency-per-leg-ms`, `--adverse-move-allowance`, and `--minimum-capturable-fraction`
- `COSTS__ADVERSE_MOVE_ALLOWANCE` and `COSTS__MINIMUM_CAPTURABLE_FRACTION` configuration
- Latency capture block in the experiment payload and a dashboard panel beside the execution verdict

### Fixed

- `EpisodeCapture.is_capturable` was inverted, so a not-capturable episode reported itself as capturable
- `COSTS__LATENCY_ASSUMPTION_MS` was passed into `CostModel` but never used in any calculation; it now drives the latency model

### Observed

- Real two-broker XAUUSD comparison reported 16 opportunity episodes, but at a 100 ms round trip only 2 were capturable. The median episode lasted 0 ms because most crossable observations were a single aligned tick, and the mean captured edge fell from 0.0513 to 0.0069, roughly a thirteenth of the peak. At a 6000 ms round trip nothing was capturable. Reporting the episode count alone overstated the result by about an order of magnitude.

## [1.5.0] - 2026-09-26

### Added

- Discovery tab in the research dashboard, reading persisted `advanced_relationship_discovery` reports
- Raw against adjusted p-value chart per candidate with the alpha threshold, making the cost of false-discovery control visible
- Per-symbol panel coverage chart with excluded symbols greyed, giving the context candidates were computed under
- Candidate table joining significance, `survived_correction`, and `contested` onto each candidate's evaluation metrics
- Explicit warning listing contested candidates where the stationarity tests disagreed
- `list_discovery_reports`, `load_discovery_report`, `candidate_frame`, and `coverage_frame` in the report loaders
- Typed report readers `as_count`, `as_float`, `as_records`, and `as_str_list` so a partially written report degrades instead of raising
- Discovery tab render tests and report loader unit tests

### Changed

- The Relationship Explorer is now captioned to distinguish the declared catalog from evaluated evidence

## [1.4.0] - 2026-09-26

### Added

- Cross-symbol coverage reporting: per-symbol observations, first and last timestamp, coverage fraction, and largest gap
- Largest-shared-window analysis so discovery runs only on genuinely comparable data
- Greedy subset selection when no symbol spans a window, because choosing by column order pairs instruments that never trade at the same time
- Actionable failure when no usable window exists, naming the problem, the affected symbols, and the remedy
- Candidate de-duplication keyed on target plus a canonical formula, reusing the existing `FormulaParser`
- Associative flattening of multiplication and addition chains before sorting, so `A*B*C` and `C*B*A` agree
- `contested` flag and count when the ADF and KPSS verdicts disagree
- `discover --minimum-symbols-for-window`
- Coverage and de-duplication sections in the advanced discovery report and provenance manifest
- Bilingual panel coverage and candidate family documentation

### Fixed

- A panel whose symbols covered different calendar ranges failed as `prices must be finite positive values` from a statistics routine, which said nothing about the misalignment that caused it. Observed on a real Alpari demo account where one nine-symbol request left USDJPY ending sixteen days before EURUSD, and zero timestamps were shared by every symbol.
- Candidates differing only in name, whitespace, or redundant grouping were counted as separate tests, inflating the family and making a false-discovery correction stricter for no reason

### Observed

- The greedy subset pass selected `EURGBP` and `EURJPY` with 1500 shared rows, where alphabetical order would have paired `GBPJPY` with `EURGBP`, which never trade at the same time
- `EURGBP_SYNTHETIC` survived correction at an adjusted p-value of 0.0013 but is contested, because its stationarity tests disagreed

## [1.3.0] - 2026-09-26

### Added

- False-discovery control across the discovered candidate family, reusing `statsmodels` `multipletests` rather than a hand-rolled procedure
- `bonferroni`, `holm`, `sidak`, `fdr_bh`, and `fdr_by` methods with `fdr_bh` as the default
- Reporting of the number of tests and the rejections expected under the null, so a surviving candidate is read against the family it came from
- Per-candidate raw and adjusted p-values, unadjusted and adjusted verdicts, and adjusted rank
- Candidates excluded from the family when their stationarity test never ran, listed separately
- `multiplicity` section in the advanced discovery report and its provenance manifest
- `discover --multiplicity-method`
- Multi-broker dashboard with a sidebar profile selector and per-profile health check
- Per-profile symbol resolution in the market monitor, reusing `SymbolMapper`
- Execution and capital verdict surfaced in the dashboard comparison views
- Streamlit `AppTest` integration suite that executes the page script
- Bilingual multiple-testing and dashboard documentation

### Fixed

- The dashboard assumed a single terminal, so a second configured demo broker was invisible
- The dashboard market monitor requested quotes using canonical research names, so it could not read an instrument a broker publishes under a different label, such as `BITCOIN`
- The dashboard market monitor requested each quote three times per row, tripling broker round-trips and able to mix values from different moments
- Replaced `use_container_width` with `width`, whose Streamlit deprecation deadline has already passed

### Observed

- Against 1370 M1 bars spanning six symbols, two candidates were testable: `EURGBP_SYNTHETIC` survived with an adjusted p-value of 0.0013, while `XAUEUR_SYNTHETIC` did not survive at 0.056
- The same relationship produced different stationarity verdicts on 300 and 1500 bar samples, so a single run is not a discovery

## [1.2.0] - 2026-09-26

### Added

- Margin model that treats a broker-reported `margin_initial` of `0.0` as *not reported* rather than free, with `broker_reported`, `leverage_derived`, and `unavailable` sources
- Fill feasibility that reduces requested volume to the broker `volume_step` and `volume_max`, reporting a partial fill instead of silently truncating
- Overnight funding accrual per night held, including the configurable triple-swap rollover weekday
- `ExecutionAssessor` combining margin and fill feasibility into a verdict with separate blocking and advisory reasons
- Execution feasibility reported in the cross-broker summary and experiment report, with a `_capital_unverified` classification suffix when margin cannot be determined
- `COSTS__` configuration for volume, leverage, funding, minimum fill ratio, and holding days
- `compare-brokers --volume`, `--leverage`, and `--minimum-fill-ratio`
- `compare-brokers --symbol-a` and `--symbol-b` for brokers that name an instrument differently
- `doctor --broker-profile` and `mt5-info --broker-profile` so every configured terminal is verifiable
- Bilingual execution and capital model documentation, including two live two-broker case studies

### Fixed

- `doctor` and `mt5-info` had no broker profile flag, so a second configured demo terminal could not be diagnosed at all
- `compare-brokers` required one symbol label for both feeds, which made cross-broker research impossible whenever broker names differ. The observed configuration publishes bitcoin as `BITCOIN` on one broker and `BTCUSD` on the other.
- `doctor` symbol discovery compared canonical names literally instead of resolving through the alias table

### Observed on two live demo brokers

- `Alpari-MT5-Demo` build 6184 leverage 500 and `AMarkets-Demo` build 6230 leverage 1000 are distinct brokers
- EURUSD contracts are compatible and produced zero crossable observations
- XAUUSD reports a ten times tick-value difference between brokers; the maximum normalized net PnL was +23.10 while the mean was -14.50
- BTCUSD is blocked by the contract gate because one broker quotes in whole dollars, so the apparent 5.98 price difference is mostly rounding rather than a dislocation

## [1.1.0] - 2026-09-26

### Fixed

- Stationarity diagnostics no longer report false-positive cointegration. The hand-rolled augmented Dickey-Fuller approximation inverted a near-singular OLS design matrix and returned a statistic of 3.7e16 with a zero p-value on real Alpari XAUEUR data, where a proper test gives ADF p=0.82 and KPSS p=0.01, both agreeing the residuals are not stationary.
- A constant residual series is reported as `unavailable` with a reason instead of returning a `-1e308` sentinel that was presented as strong cointegration evidence.
- Stationarity testing requires at least 30 aligned observations and reports `unavailable` below that.
- `recent_ticks` returns the newest ticks in the window. `copy_ticks_from` returns the oldest ticks at or after the requested time, so it silently collected stale data.
- Tick collection no longer fails outside trading hours. A search anchored at the current time returns an empty array rather than `None`, which was reported as no data.
- Blank optional configuration values such as `MT5__LOGIN=` load as "not configured" instead of failing validation, so the shipped example configuration works when copied verbatim.
- CLI output reconfigures the console to UTF-8 because broker symbol descriptions contain non-ASCII text that raised `UnicodeEncodeError` on narrow code pages.

### Added

- Alias, description, and name aware symbol discovery that reports which rule matched
- Tradability-aware filtering; a symbol with a disabled or unknown trade mode is excluded by default
- Whole-catalog search instead of only the terminal watch window, with `catalog_size` and `tradable` counts
- `symbols --visible-only`, `symbols --all`, and `symbols --json` output
- `MT5Adapter.symbol_details` reading full broker metadata in a single MT5 call
- `MT5__TICK_LOOKBACK_HOURS` and `MT5__TICK_MAX_LOOKBACK_HOURS` configuration with automatic window widening
- `kpss_p_value_is_bounded` and `unavailable_reason` fields on stationarity results
- `statsmodels` dependency replacing hand-rolled stationarity approximations
- Bilingual symbol mapping documentation with an observed broker catalog
- `.gitattributes` normalizing line endings

## [1.0.0] - 2026-09-25

### Added

- Rolling beta with warmup, sign consistency, and stability summaries
- OLS-residual cointegration proxy diagnostics
- Fixed-lag ADF and level KPSS approximation diagnostics
- Statistical results in historical and advanced candidate research reports
- Configurable rolling-beta and significance CLI/settings parameters
- Deterministic statistical tests and bilingual methodology documentation

## [0.9.0] - 2026-09-25

### Added

- Causal low, normal, and high volatility regime detection
- Directed relationship dependency hypergraph with bounded expansion
- Price-panel loader for wide and long CSV/Parquet inputs
- Historical candidate evaluation with correlation, discrepancy, persistence, and regime metrics
- Deterministic NumPy ridge ranking with chronological train/evaluation split
- `discover --input` advanced research workflow and provenance reports
- Bilingual advanced-discovery documentation and deterministic tests

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
