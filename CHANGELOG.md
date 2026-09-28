# Changelog

All notable changes follow semantic versioning.

## [Unreleased]

### Fixed — funding

- The triple-swap multiplier applied only when the whole holding period was
  exactly one night, so a position held from Wednesday to Friday was charged 2x
  instead of 3x for the Wednesday rollover plus 1x for the night after — a third
  of what it owed. Every triple-swap rollover inside the held interval is now
  counted, giving `nights + 2 * rollovers`, and a hold long enough to cross two
  rollovers is charged for both
- `annualized_rate` was set to the configured **daily** fraction, so a field
  named for an annual figure understated the annual cost 365-fold and invited
  comparison against an annual rate quoted elsewhere. It now reports
  `daily * 365`, and a new `daily_rate` field publishes the configured figure so
  the report is unambiguous. Both report `None` when no rate is configured
  rather than `0.0`, because zero overnight funding is not a measurement of
  free capital, and a period that accrues nothing still reports the rate so
  "closed in the same session" stays distinguishable from "no rate configured"

### Fixed — latency capture

- The captured edge was the value at the instant the round trip completed, not
  the mean over the window in which the position is actually held. Once both
  legs are open the position is held until the edge closes, so the expectation
  is the average of what remains; the old figure is the best case anywhere in
  the window presented as the expected one, and under linear decay it is exactly
  double. On a 1000 ms episode with a 100 ms round trip and a peak of 1.0 at the
  start, the reported captured edge was 0.9 and is now 0.45
- The producer took the maximum edge over an episode and the model assumed it
  occurred at the start, so the model credited the position with an edge as large
  as the peak across the whole window no matter when the peak arrived. Episodes
  now carry `peak_offset_ms`, the measured position of the maximum, and the
  profile rises linearly from zero to the peak at that offset before decaying,
  which is the lowest profile consistent with the measurements. On the same
  episode with the peak arriving at 900 ms, the optimistic figure of 0.9 becomes
  0.549. The rising segment is an assumption, not a measurement, and is stated
  in the module and in `EXECUTION_MODEL.md`
- `capturable_fraction` and the capturable verdicts are unchanged: they describe
  the window, not the edge profile. Only the edge magnitude is corrected
- A persisted capture report without `peak_offset_ms` cannot be reproduced
  faithfully, so the sensitivity sweep drops those episodes rather than assuming
  the peak sat at the start and quietly contradicting its own baseline. An
  offset that cannot lie inside its episode is dropped for the same reason
  instead of raising, following the reader's existing convention for other
  absent fields

### Fixed — execution feasibility

- `ABOVE_MAXIMUM` was never a blocking reason, so a leg the broker demonstrably
  cannot fill in full passed the `executable` gate and the pair was reported as
  executable. A 50-lot request capped at 10 lots on one broker, with the other
  leg taking its full size, returned `executable = True` with an empty
  `blocking_reasons` and a binding fill ratio of 0.2. That is not the researched
  pair at reduced size: it is a net directional position on the uncapped broker,
  and the discrepancy was computed for a specific size. `above_maximum` is now
  a blocking reason on either leg. This reverses a documented verdict — the
  earlier reasoning that PnL scales with filled volume is true of a single leg
  and wrong of a cross-broker pair — so `EXECUTION_MODEL.md` states the
  corrected convention, and the reduced size is still reported through
  `binding_fill_ratio` rather than discarded
- `minimum_fill_ratio` defaulted to `0.0`, a floor no fill ratio can fall below,
  so the check appeared in every report and could never block anything. Rounding
  a request down to `volume_step` cannot produce a ratio at or below one half,
  so any threshold of `0.5` or less is unfalsifiable rather than merely
  lenient; the observed floor across step and size combinations is about 0.51.
  The default is now `0.9`, exported as
  `costs.execution.DEFAULT_MINIMUM_FILL_RATIO` and shared by `CostSettings`,
  `CrossBrokerRequest`, and the assessor so the three cannot drift apart. A
  configuration that relied on `0.0` or `0.5` to mean "do not gate on size" must
  now set it to `0.0` explicitly to restore that
- A `volume_max` that is not a whole multiple of `volume_step` was rounded down
  and could produce `filled_volume = 0.0` with `partial_fill = True` and status
  `above_maximum`: a claim of a partial fill of nothing. A cap that leaves the
  achievable size below `volume_min` is now refused as `below_minimum` with
  `limited_by` naming the cap

### Fixed — statistical measurement

- The Engle–Granger step 2 p-value used the MacKinnon table for a regression
  with zero predetermined regressors, which is the wrong distribution for a
  residual series that was produced by a regression containing one. The
  reported p-value was anti-conservative by roughly a factor of two, so a pair
  whose residual is a near unit root came back significant at the 5% level. On
  one such pair the unadjusted p-value read 0.027 and the adjusted one 0.090,
  and the verdict `cointegrated_at_significance` followed the wrong one. That
  figure fed `engle_granger_p_value`, which is exactly what the false-discovery
  family consumes, so the bias was inherited by the correction applied across
  the family. The test now runs through `statsmodels.tsa.stattools.coint` and
  reports the regressor-adjusted p-value; the unadjusted value is reported
  alongside as `adf_p_value_without_regressor_adjustment`, and
  `adf_p_value_is_regressor_adjusted` states which one drove the verdict
- A pair that is so nearly collinear that the benchmark explains almost all of
  the target variance made `coint` return a statistic of `-inf` with a p-value
  of zero, which its own documentation calls numerically unstable rather than a
  test result. Reporting that zero would have certified a cointegrated
  relationship the test never measured, so such a pair is now reported as
  `unavailable` naming collinearity as the reason. The detection uses the same
  R-squared criterion `coint` applies, so a genuinely cointegrated pair is
  still evaluated

## [1.9.0] - 2026-09-28

This release corrects measurement defects found in a full audit of the research
pipeline. Every item below produced a number that looked valid but was wrong, or
turned a failure into a favourable-looking result. The 274 tests at 1.8.1 passed
while all of these were present.

### Fixed — cross-broker measurement

- Event-time alignment searched an unsorted array. A feed whose rows arrived out
  of chronological order matched each tick to the wrong neighbour, silently
  discarded observations, reported the delay as zero, and could report a
  physically impossible opportunity rate of 3600/hour. Timestamps are now sorted
  once with a monotonicity check
- Opportunity episodes were grouped by adjacent row index rather than by
  wall-clock time, so two crossable instants minutes apart were reported as one
  long opportunity and then declared `capturable` against the round trip
- Episode continuity now uses the feed's own tick cadence, exposed as
  `maximum_episode_gap_ms`; an episode with a single observation reports zero
  duration
- Non-finite and empty broker frames are rejected explicitly instead of passing
  the price checks or being reported as a symbol mismatch
- Persisted preview column order no longer varies with `PYTHONHASHSEED`

### Fixed — money and risk figures

- `ContractEdgeNormalizer` valued the combined two-leg edge against both legs
  and summed them, roughly doubling a symmetric opportunity. A cross-broker
  position realizes the price difference once; the two legs are now reported as
  the two independent valuations they are, and their disagreement beyond 5%
  raises `_contract_legs_disagree` instead of being added
- `confidence_max_drawdown` read the wrong quantile for a negative-signed series
  and reported the shallowest of the worst cases as the confidence bound, milder
  than a typical drawdown
- `ResearchBacktester` measured drawdown without a zero seed, so a curve opening
  below its own high reported no drawdown at all, and disagreed with the Monte
  Carlo simulator that computes the same quantity correctly
- `win_rate` and `average_return` were averaged over every bar while
  `opportunities` counted only traded bars. They are now measured over the trades
  taken, with `observation_win_rate` added for the all-bars population
- Adverse/favourable excursions were sums of gross values rather than
  peak-to-trough excursions, on a different basis from the drawdown beside them
- Walk-forward aggregates concatenated overlapping test windows, reporting a
  larger out-of-sample sample than existed and a drawdown over a doubled,
  out-of-order equity path
- The adverse-move sensitivity sweep never identified its own baseline, so every
  sweep reported `nominal` regardless of result, and its curve was flat along the
  axis being swept
- A missed trade in the Monte Carlo stress scenarios refunded its cost, which
  discounted the scenario's cost multiplier by the missed fraction and could make
  a stress scenario beat the baseline

### Fixed — look-ahead and single-candidate fragility

- The ridge ranker trained on `pearson`, `spearman`, and `half_life` summarised
  over each candidate's whole series, so the out-of-sample score was computed
  against features containing the evaluation period. Replaced with an
  expanding-window correlation computed causally per row
- A ninth ranking feature was identically `1.0` for every row and is removed
- Warm-up z-scores filled with `0.0`, recording the absence of a discrepancy as a
  perfect score; they are now undefined and excluded by the ranker
- The expanding correlation was numerically unstable on price-level data and
  could flip sign; it is now centred before accumulation, clipped to its own
  bounds, and tested against a direct pandas computation
- One non-positive price or one zero denominator aborted an entire discovery run
  instead of degrading a single candidate, which affected every additive
  relationship whose target crosses zero
- A zero denominator now invalidates one observation rather than the whole
  candidate

### Fixed — demo-only guarantee

- The verified `DEMO` account mode was cached for the life of the adapter. The
  terminal is a separate long-lived process that can be re-logged-in mid-session,
  so a snapshot cached that long kept certifying an account the operator had
  switched away from, and that mode is written into every dataset manifest.
  Re-verified on a configurable TTL, `MT5__ACCOUNT_VERIFICATION_TTL_SECONDS`
- `is_connected` only tested that an import succeeded; it now probes the terminal
  so a session closed elsewhere is not reported as connected
- `DemoSafetyError` was collapsed into a generic connection failure in both
  `doctor` and the dashboard, sending an operator to debug a working terminal.
  It now has its own `demo_safety_refused` status and its own banner
- `doctor` raised `ImportError` when the `MetaTrader5` package was absent — the
  exact case the check exists to report
- A failed terminal shutdown is logged rather than raised, because `disconnect`
  also runs on context exit
- Reconnecting no longer keeps the previous session's handle and snapshot

### Fixed — malformed reports rendered as findings

- `as_count` and `as_float` returned `0.0` for absent fields, rendering a report
  with no assumptions block as "round trip 0 ms" — the most capturable result the
  model can produce — and stating that no episode outlasted the round trip
- `as_count` raised on JSON `NaN`, which Python's `json` module emits by default
- A candidate missing from the multiplicity family was reported as having failed
  correction, presenting a schema problem as a rigorous negative result
- An unrecognized fragility class fell through to "the verdict holds across the
  whole swept range"
- `step_observations=0` was silently replaced with the test size

### Added

- `maximum_episode_gap_ms` request field, and the resolved value in the manifest
- `normalized_pnl_legs_agree` and `normalized_pnl_leg_disagreement_ratio`
- `test_windows_overlap` and `duplicate_test_trades_removed` on walk-forward
  results
- `observation_win_rate` alongside the trade-level `win_rate`
- `hypothesis_recorded` in the discovery candidate frame

## [1.8.1] - 2026-09-27

### Added

- Proven semantic equivalence for monomial rational formulas such as `A/(B*C)`, `A/B/C`, and `(A/B)*B`
- Two-stage semantic-then-syntactic candidate de-duplication with explicit merge reporting
- Advanced-discovery manifest fields for semantic merges and equivalence basis

## [1.8.0] - 2026-09-27

### Added

- Measured round-trip latency baselines read from CSV, Parquet, or JSON execution logs
- Latency statistic, symbol, and broker filters with zero-round-trip refusal
- Measured latency provenance, related-source hashing, and report metadata
- Dashboard banner distinguishing measured latency from an assumption

### Fixed

- Dashboard latency and execution renderers now receive the report explicitly instead of relying on a module global

## [1.7.1] - 2026-09-27

### Fixed

- Package metadata now reports `1.7.1` consistently; experiment manifests were still stamped `1.0.0` while the distribution reported `1.7.0`
- Near-zero OLS residuals are reported as `unavailable` for cointegration diagnostics instead of running singular ADF/KPSS regressions

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
