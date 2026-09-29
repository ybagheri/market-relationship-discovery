# Roadmap

Status: `[ ] Planned`, `[~] In progress`, `[x] Completed`, `[!] Known defect`.

This file is the map of where the project stands. Read it before changing
anything: the phases below are marked complete against the behaviour described,
and a complete item that is listed under **Open corrections** is complete in form
but not in fact.

A point-in-time record of the most recent session's corrections, the judgement
calls behind them, and what remains is in the
[handoff](HANDOFF.md). The roadmap is the map; the handoff is the state of play.

## Where the project stands

The research platform is feature-complete through the phases below. What is
deliberately absent is order execution, which is out of scope by design and
recorded as such in `SECURITY.md`.

The current work is not new capability. It is measurement correctness. A full
audit of the pipeline found a class of defects that share one shape: the code
produced a number that looked valid, carried it into a report, and let it be read
as evidence. A passing test suite did not catch any of them, because in every
case the test asserted that the pipeline produced a well-formed result, not that
the result was true. Version 1.9.0 corrects the ones that were found; the
remaining ones are listed below rather than left implicit.

## Phase 0 — Foundation

- [x] Audit the initially empty repository
- [x] Establish package, typed configuration, and logging
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
- [x] Chronological ordering established once at load, with a monotonicity check
- [x] Non-finite and empty frames rejected explicitly rather than passing price checks

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
- [x] Every triple-swap rollover inside a multi-night hold counted
- [x] Funding reports the daily rate and its annualized equivalent separately
- [x] Execution feasibility verdict integrated into the cross-broker summary
- [x] A `volume_max`-capped leg blocks the pair instead of passing the `executable` gate
- [x] `minimum_fill_ratio` default above the unfalsifiable 0.5 bound, shared across settings, request, and assessor
- [x] A `volume_max` that is not a step multiple reports the refused size instead of a zero fill
- [x] Latency capture against measured episode duration with a capturability gate
- [x] Captured edge reported as the mean over the holding window, not its first instant
- [x] Episode peak carries its measured offset instead of being assumed to occur at the start
- [x] Latency and adverse-move sensitivity sweep with fragility classification
- [x] Measured round-trip latency from an execution log, replacing the assumption
- [x] Per-broker symbol labels so cross-broker research survives differing names
- [x] Opportunity episodes bounded by wall-clock continuity, not row adjacency
- [x] Cross-broker edge valued once, with leg disagreement reported
- [~] Queue position and book depth, which research data cannot observe

## Phase 5 — Statistical Research

- [x] Pearson and Spearman correlation
- [x] Rolling z-score
- [x] Half-life and lead/lag
- [x] Rolling beta and stability
- [x] Cointegration and stationarity tests using `statsmodels` ADF and KPSS
- [x] Explicit unavailable reasons for degenerate or too-short residual series
- [x] Multiple-testing adjustment across discovered candidates
- [x] Cross-symbol coverage reporting and largest-shared-window analysis
- [x] Candidate-family de-duplication by canonical formula
- [x] Contested flag when stationarity tests disagree
- [x] Semantics-aware formula equivalence beyond syntactic canonicalisation
- [x] ADF p-value adjusted for the cointegrating regressor, via `statsmodels` `coint`
- [x] Near-collinear pairs reported as unavailable rather than as a zero p-value
- [!] Regime frequencies are pinned by the quantile method rather than measured
- [!] Redundant and misleading multiplicity report fields

## Phase 6 — Discovery Engine

- [x] Candidate generation framework
- [x] Data-driven ranking and robustness filters
- [x] Causal ranking features only; no whole-sample statistic enters the model
- [x] One malformed candidate degrades to a status instead of aborting the run
- [x] `A-B` parses as a subtraction; a hyphenated broker name is written quoted
- [x] Formula rendering round-trips: a rendered formula re-parses to the same identity
- [x] A generated candidate is not reported as evaluated when it was not
- [x] Bounded candidate family, with the truncation reported
- [x] `generate` declares a synthetic target rather than inflating `REQUIRES_DATA`

## Phase 7 — Backtesting

- [x] Basic deterministic cost-aware metrics
- [x] Next-observation signal execution without same-timestamp leakage
- [x] Walk-forward train/validation/test folds and train-only threshold selection
- [x] Causal multi-stage signal ensemble
- [x] Experiment IDs, source hashes, and JSON reports
- [x] Circular block-bootstrap Monte Carlo robustness
- [x] Wider-spread, slippage, latency, and combined stress scenarios
- [x] Drawdown measured from the starting equity, consistent across both paths
- [x] Win rate and average return measured over the trades actually taken
- [x] Overlapping test windows de-duplicated in the aggregate
- [x] Stress scenarios that cannot improve on the baseline
- [!] Validation fold metrics are computed and never used
- [!] `minimum_train_observations` gates on trade count, not train observations
- [!] A NaN episode duration yields a `capturable` verdict

## Phase 8 — Dashboard

- [x] Persistent demo/research warning
- [x] Overview, monitor, catalog, and limitations views
- [x] Interactive discrepancy and broker charts
- [x] Multi-broker profile selection with per-profile symbol resolution
- [x] Per-profile health check that reports failure as data
- [x] Execution and capital verdict surfaced from persisted reports
- [x] Script-level render tests through Streamlit AppTest
- [x] Evaluated discovery results surfaced with significance, contested flags, and coverage
- [x] Absent, mistyped, and non-finite report fields render as unknown, never as zero
- [x] Unrecognized fragility classes are not reported as a passing result
- [!] Unreadable report files are indistinguishable from a missing one
- [!] A single unavailable symbol discards every row in the monitor

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
- [!] Collected datasets may retain duplicate tick timestamps
- [!] Manifest window is taken from raw inputs, not the aligned sample

## Phase 10 — Optional Execution

- [ ] Not implemented and explicitly out of scope; a separate execution package and authorization are required
- [ ] If separately authorized later: demo-only, kill switch, exposure/loss limits, audit trail

## Open corrections

Every item here was found by the audit and has not been fixed. Each produced a
plausible-looking number rather than an error, which is why it survived a
green test suite. They are ordered by how much a reader could be misled.

The ADF p-value item was corrected after this list was written. The correction
also exposed a second condition in the same function: a pair that is nearly
collinear makes `coint` return a statistic of `-inf` with a p-value of zero,
which it documents as numerically unstable rather than as a test result. That
case is now reported as `unavailable` naming collinearity, because reporting the
zero would have certified a cointegrated relationship the test never measured.

The fill-feasibility item changed a documented verdict rather than only a
number. A capped leg was previously argued to stay executable because PnL scales
with filled volume, which is true of one leg and wrong of a cross-broker pair,
where a cap on one side leaves a net directional position. `above_maximum` is
now a blocking reason. `EXECUTION_MODEL.md` states the corrected convention.

The contract item changes a verdict for the same reason. The pair was previously
argued to stay comparable because volume normalization can reconcile a lot-size
difference, and that argument holds only when `tick_value` scales with
`contract_size`. When it does not, the two legs disagree at every volume, so
normalization cannot reconcile them and the pair is now refused. This also makes
the documented legs-agree check a backstop rather than the primary gate. The
figures `EXECUTION_MODEL.md` quotes from the 2026-09-26 Alpari/AMarkets run fall
on the refused side of this line, so they are labelled as produced by the earlier
model rather than restated.

The capture-formula item separates two quantities the model had merged. The
capturable fraction answers *when* the position can be held and depends only on
time, so the verdicts are unchanged. The captured edge answers *how much* is in
that window, and the old formula reported the value at the first instant rather
than the mean across it, which is twice the expectation under linear decay. The
producer also took the peak from anywhere in the episode while the model treated
it as the starting value, so episodes now carry the measured offset.

The formula-tokeniser item turned out to be two defects and one of them was not
in this list. The listed defect is real: `-` inside the identifier class made
`A-B` a single symbol that cannot exist in a panel, so the subtraction was
discarded. Removing `-` alone would have been a second wrong answer, because the
discovery engine interpolates live broker names into formula text and brokers do
publish hyphenated names — those would have become silent subtractions. A name
containing a hyphen is now written quoted, and every renderer of a formula quotes
a name that would otherwise be ambiguous, so a formula always re-parses to the
identity it was rendered from. The unlisted defect is that the monomial identity
key joined names with `,` and `^` unescaped, which quoting would have turned into
a way to forge another formula's key and merge two hypotheses during
de-duplication.

### High — a reported figure is wrong

- [x] `relationships/formula.py` — `-` inside the identifier class made `A-B` a
      single symbol name, so an un-spaced subtraction became a dependency that
      can never exist in a panel. Corrected with quoting for names that
      genuinely contain a hyphen, and with an escaped identity key
- [x] `market_data/contract.py` — a broker that halves `contract_size` without
      halving `tick_value` is not describing the same instrument, and the pair is
      now refused instead of normalized
- [x] `discovery/engine.py` — `filter` overwrites `REQUIRES_DATA` with
      `INSUFFICIENT_OBSERVATIONS`, and the `permutations(..., 3)` family is O(n³)
- [x] `costs/analyzer.py` — `CostAwareAnalyzer` and `CostModel` had no caller
      and the model held a latency assumption it never applied. Removed rather
      than wired in, because the single-symbol path deliberately claims no
      executable discrepancy; a cost component belongs where it is charged

### Medium — a failure is presented as a favourable result

- [x] `parallel_collection.py` — raising inside the executor drained the pool on
      shutdown while workers kept writing datasets, and `DataQualityError` was
      retried three times, each attempt minting a new `dataset_id` and orphaning
      the previous output
- [x] `parallel_collection.py` — a `DemoSafetyError` in parallel mode is wrapped
      as `ParallelCollectionError`, so a safety refusal is indistinguishable by
      type from a transient connection error
- [x] `market_data/panel.py` — `read_csv` inferred dtypes, so a symbol code like
      `000300` became the integer `300` and could never join to a broker label
- [x] `validation/quality.py` — a string price column raised `TypeError` instead
      of `DataQualityError`, and duplicate counting ran across the whole frame,
      so a legitimate two-symbol tick file was reported invalid
- [x] `market_data/alignment.py` — `align_timeseries` returned unmatched rows
      with a `NaT` delay, so the frame was larger than its evidence. It now
      returns only matched rows and reports the unmatched counts. The three
      alignment implementations are not merged: the symmetric event-time match
      is a deliberately different rule, documented in `DATA_QUALITY.md`
- [x] `cli.py` — `symbol-specs` writes a JSON list, which `compare-brokers`
      rejected whenever more than one symbol was requested. The compared symbol
      now selects its entry, and an unmatched or ambiguous file names the
      symbols it actually contains
- [x] `market_data/symbols.py` — alias matching was substring-based, so `XAUUSD`
      matched `XAUUSDmicro` and the winner was whichever symbol the broker listed
      first. Aliases now match at a word boundary and results are ranked by match
      quality rather than catalog order

### Low — hygiene with real consequences

- [x] `market_data/contract.py` — a differing `volume_max` alone was treated as
      `incompatible` and blocked the comparison, although the cap is enforced
      per leg by the fill assessor. It is now an advisory, reported beside the
      verdict rather than blocking it
- [x] `config/settings.py` — `DataSettings.timezone` was half of a critical
      `doctor` verdict that no data path honoured; `cache_enabled` and
      `cache_directory` were read by nothing; `latency_log_statistic` was an
      unvalidated string the CLI ignored. The timezone now selects a report's
      display timezone and is not part of the safety verdict, the two unused
      cache settings are removed, and the statistic is validated
- [x] `config/settings.py` — two broker profiles may point at the same terminal
      and collect it twice under different labels, letting a comparison pair a
      broker with itself. Refused at load time, comparing resolved paths
- [ ] `statistics/analyzer.py` — `correlation` accepts three observations;
      `half_life` has no plausibility bound; `lead_lag` has no documented sign
      convention or significance; `rolling_correlation` has no caller
- [ ] `statistics/analyzer.py` and `backtesting/multi_stage.py` — two identical
      copies of the rolling z-score used as model input
- [ ] `backtesting/engine.py` — the no-look-ahead guarantee rests on an
      undocumented column convention: that `gross_edges[t]` is the return earned
      over `[t, t+1]`. If it is the edge realised at `t`, `shift(-1)` is itself the
      look-ahead
- [ ] `backtesting/walk_forward.py` — `self._splitter` stores the class, not an
      instance, so there is no seam for a test double
- [ ] `infrastructure/storage/quotes.py` — the Parquet file is moved to its final
      path before the manifest is written, so a manifest failure orphans a dataset
- [ ] `cli.py` — `_serializable` raises a context-free `TypeError` for NumPy
      scalars; `_dashboard` has no child-process lifecycle management
- [ ] `market_data/cross_broker.py` — `maximum_*_crossable_edge` is not gated on
      the execution verdict, so it can report a crossable edge beside
      `crossable_observations = 0`

## How to continue

1. Run the quality gate first: `pytest`, `ruff check .`, `black --check .`, `mypy`.
2. Take items from **Open corrections** in order. Each is a small, self-contained
   change with a regression test that fails before it.
3. Move the item from **Open corrections** to its phase as `[x]`, and add a
   `CHANGELOG.md` entry describing what number was wrong, not just what changed.
4. If a change alters a reported figure, update the corresponding document under
   `docs/research/`. Those documents state conventions, not just usage, and a
   convention that changes without them being updated is how the defects above
   survived.
