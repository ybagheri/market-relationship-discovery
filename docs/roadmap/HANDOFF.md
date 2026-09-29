# Handoff — audit corrections continued, 2026-09-29

This is a handoff record, written so that a later session or another system can
resume the work without reconstructing it. The previous session's record is
preserved verbatim as [HANDOFF-2026-09-28.md](HANDOFF-2026-09-28.md); this file
covers the items it handled. It is a point-in-time snapshot; the
[roadmap](ROADMAP.md) remains the map of where the project stands.

## Where things stand

**Every item in the audit's High list is now corrected**, committed, and pushed
state recorded on `main`. The quality gate is green.

| Check | Result |
| --- | --- |
| `pytest` | 375 passed |
| `ruff check .` | clean |
| `black --check .` | clean |
| `mypy` (strict) | clean, 69 source files |

Nothing is skipped now. The MT5 terminal test runs because `.env` configures two
live demo terminals, and the dashboard discovery test runs because
`examples\prices.csv` exists. Both depend on local configuration, so a fresh
checkout without a terminal will skip the MT5 test again.

Commits for this session, oldest first:

| Commit | Item |
| --- | --- |
| `15f909f` | Read an un-spaced hyphen as subtraction, not a symbol name |
| `e8286d0` | Refuse a contract pair whose size and tick value do not scale together |
| `55c007c` | Do not report an unevaluated candidate as measured, and bound the family |
| `954ff1d` | Remove the cost model that no calculation used |
| `82eb5dd` | Handoff record for the High list being cleared |
| `a58e9f8` | The price panel the quick start refers to |
| `315f9fa` | Test count correction |
| `623e724` | Drain the collection pool before reporting a failure; keep the safety refusal distinguishable |
| `14b0205` | Let `compare-brokers` use a multi-symbol contract export |

Test count went from 324 to 375. Each correction added regression tests that fail
against the code as it was before the change; the removed cost model took its one
test with it and was replaced by three stronger ones.

## What was wrong, and what is different now

### 1. `A-B` was one symbol name

`-` was an identifier character, so the un-spaced subtraction `A-B` tokenised as
a single symbol that cannot exist in a price panel. The evaluator reported the
candidate as `requires_data` with a `missing_symbols` entry for a symbol that was
never requested, and the subtraction was discarded without a word. It reached
further than the roadmap recorded: `XAU-USD/USD-USD` also produced a phantom
`USD-USD` dependency, and `X-B-A` collapsed entirely.

**Removing `-` alone would have been a second wrong answer.** The discovery engine
interpolates live broker names into formula text, and brokers do publish
hyphenated names, so a bare `XAU-USD` would have become a silent subtraction. A
name that genuinely contains a hyphen is now written quoted, and every renderer
of a formula — candidate generation, the de-duplication canonical form, and the
semantic key — quotes a name that would otherwise be ambiguous, so a formula
always re-parses to the identity it was rendered from.

Quoting then made `,` and `^` reachable inside a name, and the monomial identity
key joined names with those characters unescaped, so two different formulas could
forge one key and be collapsed into a single hypothesis during de-duplication.
That is a second defect the roadmap did not list.

### 2. A contract pair that no volume can reconcile

A broker that halved `contract_size` without halving `tick_value` was accepted as
`normalization_required`, so the pair passed the contract gate, a normalized PnL
was reported beside an otherwise crossable opportunity, and the inconsistency
surfaced only as an advisory `_contract_legs_disagree` suffix.

Both fields scale the same quantity — the money value of one unit of the
underlying, `tick_value / (tick_size * contract_size)`. When only one moves, the
two legs value the same position differently at *every* volume, so the pair is
now `incompatible` and blocks.

### 3. An unevaluated candidate reported as measured

The observation gate relabelled every candidate that had never been evaluated as
`insufficient_observations`, which is a claim that it *was* evaluated and the
panel held too few rows. Because `generate` set `observations = 0` on everything
it minted, `discover` reported its entire output as measured-and-rejected.

The three-symbol family also grew as n(n-1)(n-2) with no bound — 40 symbols
produced 59,280 candidates — and every one would have entered the false-discovery
family. Generation is now bounded and reports what the bound removed.

### 4. A cost model nothing charged

`CostAwareAnalyzer` and `CostModel` had no caller. The only reference was a test,
so the test asserted that a cost model subtracted costs while nothing in the
research pipeline subtracted any. Removed rather than wired in — see the
judgement calls below.

### 5. A failure tore down the collection pool

A worker failure was raised from inside the `with ProcessPoolExecutor` block, so
the exception unwound into the executor's own shutdown: the pool stopped while
the other workers were still writing datasets, so a failed run both reported an
error and left half-written output on disk. `DemoSafetyError` was wrapped as
`ParallelCollectionError`, so a safety refusal became indistinguishable by type
from a transient connection error. `DataQualityError` was retried three times,
and each attempt re-ran the whole request with a fresh `dataset_id`, orphaning
every superseded dataset.

### 6. A contract export could not be read back

`symbol-specs` writes a list, one entry per requested symbol, and
`compare-brokers` accepted a list only when it held exactly one entry. Exporting
specs for the several symbols a cross-broker study needs produced a file the
comparison rejected as corrupt. Found against the live brokers, where the
four-symbol export was unusable for every comparison.

## Verified against live brokers

`.env` now configures two demo terminals, and both were exercised. They are
**distinct brokers** despite both being Alpari-branded: `Alpari-MT5-Demo` and
`AMarkets-Demo`. Both verified `DEMO` through `doctor`.

| Check | Result |
| --- | --- |
| `doctor --broker-profile ALPARI_1` | all OK, `Alpari-MT5-Demo`, build 6230, leverage 500 |
| `doctor --broker-profile ALPARI_2` | all OK, `AMarkets-Demo`, build 6230 |
| Catalog size | ALPARI_1: 879 symbols / 128 tradable; ALPARI_2: 521 / 521 |
| Parallel collection | 4 datasets across 2 profiles, no orphans |
| `compare-brokers` EURUSD | `compatible`, mean difference 7.6e-05, 0 crossable |

**The contract correction is confirmed on real data.** XAUUSD and XAGUSD report
the same `contract_size` (100) on both brokers but a ten-times different
`tick_value` — 0.1 against 1.0 — so `tick_value / (tick_size * contract_size)` is
0.1 against 1.0. The corrected gate refuses both as `incompatible`. Under the old
rule they passed as `normalization_required` with a normalized PnL reported beside
a crossable opportunity. EURUSD is `compatible`, as expected.

**A new open question was found by this data.** WTI has identical `contract_size`
(1000), `tick_size`, and `tick_value` (10) on both brokers and differs *only* in
`volume_max`: 5 lots on Alpari against 100 on AMarkets. That is one instrument
with a different size limit, not two instruments, and a study at a size both
brokers accept is valid — yet the pair is reported `incompatible` and blocked. The
cap is already enforced per leg by the fill assessor, so blocking the whole
comparison is stricter than the evidence requires. This is recorded as an open
decision under **Low** in the roadmap, not fixed here, because it changes a
documented verdict and the right answer is a research judgement.

**Symbol naming differs per broker, as expected.** The platforms are Forex on
both; metals are `Metals\Spot Metals` on ALPARI_1 and `Metals CFD` on ALPARI_2;
oil is `WTI`/`BRN`/`NG` versus `WTI`/`BRENT`/`NGAS`; crypto is `BITCOIN` versus
`BTCUSD`; indices are `US30`/`NAS100` versus `DowJones30`/`Nasdaq100`. The
substring alias match produces nonsense on this data — `LAS VEGAS SANDS CFD`
matched a search for oil and `SILVER WHEATON CFD` matched silver — which is the
alias-matching defect already listed under **Medium** in the roadmap, and it is
the reason the catalog must be searched by path and exact name.

## Five judgement calls that need review

These are not mechanical corrections.

**A hyphenated broker name must now be quoted.** Anyone with a hand-written
formula naming a hyphenated instrument has to change it to `"XAU-USD"`. There is
no unquoted spelling, because allowing one would reintroduce the original defect.
*Worth checking:* any saved formula, catalog entry, or external configuration
using a hyphenated name. The `render_symbol` helper is the way to produce one.

**A contract pair that does not scale together is refused rather than normalized.**
Two related documented verdicts changed, and both were defensible when written:
a lot-size difference was argued to be reconcilable by volume (true only when
`tick_value` scales with it), and the leg-disagreement check was argued to be a
sufficient safety net. The corrected rule uses a 1% tolerance, deliberately
tighter than the 5% leg tolerance, because it compares two numbers describing the
same instrument rather than two valuations of a market outcome.
*Worth checking:* the `EXECUTION_MODEL.md` figures from the 2026-09-26
Alpari/AMarkets run, which now fall on the refused side of this line and are
labelled as produced by the earlier model rather than restated.

**`generate` returns a `CandidateFamily`, not a list.** This is a signature
change to a public method. The size and truncation of a candidate family are
results, not an implementation detail, but any caller doing
`for candidate in engine.generate(...)` must now read `.candidates`.

**The candidate family is bounded at 500 by default.** The bound is a research
judgement, not a measurement, and changing it changes which candidates are tested
and therefore the multiple-testing result. Truncation is deterministic and
reported as `family_truncated`. *Worth checking:* whether 500 is the right
default for the intended panel sizes, and whether a `SYNTH_`-prefixed target
should be materialised rather than declared.

**The cost model was removed, not wired in.** The single-symbol research path
deliberately reports `executable_discrepancy_claimed = False` and computes no net
edge, so giving it a cost model would have contradicted that decision. A cost
component now belongs where the edge it affects is computed.
*Worth checking:* if a single-symbol cost-aware net edge was ever intended, that
is a feature decision and not a bug fix.

**A differing `volume_max` still blocks, and that may be too strict.** Found on
live WTI data: identical contract, different size cap, currently reported
`incompatible`. Recorded as an open decision rather than changed here, because
loosening a safety gate is a research judgement and not a mechanical correction.
*Worth deciding:* whether a size bound belongs to the fill-time gate alone.

## Environment note

`.env` is now configured with the two live demo terminals and is gitignored, so
a later session on this machine has them without re-deriving the paths.
`config/specs/*` is gitignored too: captured specifications are machine-specific
local inputs containing terminal paths.

The venv the 2026-09-28 session created is gone. Only the embeddable
`python-3.13.12` distribution is installed on this machine, and it has no `venv`
module, so a project virtualenv cannot be created here. The full dependency set
from `requirements.lock` is present in that interpreter's `site-packages` and the
gate runs against it directly:

```powershell
$env:PYTHONPATH=""
& "C:\Users\bagheri\Downloads\python-3.13.12-embed-amd64\python.exe" -m pytest -q
& "C:\Users\bagheri\Downloads\python-3.13.12-embed-amd64\python.exe" -m ruff check .
& "C:\Users\bagheri\Downloads\python-3.13.12-embed-amd64\python.exe" -m black --check .
& "C:\Users\bagheri\Downloads\python-3.13.12-embed-amd64\python.exe" -m mypy
```

`git` is not on `PATH` either; it lives at
`C:\Users\bagheri\AppData\Local\Programs\Git\cmd`.

## What to do next

Follow the process in the [roadmap](ROADMAP.md): run the gate, take items from
**Open corrections** in order, each with a regression test that fails before the
fix, move the item into its phase, add a changelog entry describing what number
was wrong, and update the document under `docs/research/` whose convention
changed.

Remaining counts: **0 High, 4 Medium, 10 Low**, plus 2 Phase 10 items that are
deliberately out of scope.

The next item, first under **Medium**:

`market_data/panel.py` — `read_csv` infers dtypes, so a symbol code like
`000300` becomes the integer `300` and can never join to a broker label. The
broker catalogs make this concrete: instrument codes with leading zeros are
common enough that a silently coerced column is a live hazard, not a theoretical
one. Fix it by reading the symbol column as text, and pin it with a test that a
leading-zero code survives a round trip.

The alias-matching item, second under **Medium**, is the one the live catalogs
make most urgent: a substring search for oil returns `LAS VEGAS SANDS CFD` and a
search for silver returns `SILVER WHEATON CFD`, because those tickers contain the
alias as a substring of an equity name. The winner is also whichever symbol the
broker listed first, which is not a rule a researcher can reproduce.

## Things to be careful about

- **Check the attribution, not just the description.** Several roadmap entries
  name a file that no longer holds the described code, and this session removed
  one file outright.
- **Do not accept a test that only asserts a well-formed result.** Every defect
  in this list survived a green suite precisely because the test checked the
  shape of the output rather than its truth. A new test should fail against the
  pre-change code, and it should fail for the right reason.
- **Verify a new test against the old code before committing.** Stashing the
  source change and re-running is the only way to know a test fails for the
  defect rather than for an import error or an unrelated assertion.
- **Prefer a stated reason over a silent default.** Where an input is missing or
  unusable, the corrected code now reports the reason rather than assuming a
  convenient value.
- **Changing a reported figure means changing a document.** Three items this
  session altered numbers or verdicts that `docs/research/` states as
  conventions, and one of those invalidated a recorded observation.

