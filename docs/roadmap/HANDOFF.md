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
| `pytest` | 362 passed, 1 skipped |
| `ruff check .` | clean |
| `black --check .` | clean |
| `mypy` (strict) | clean, 69 source files |

The remaining skip is environmental, not a failure: one MT5 terminal test with no
configured terminal path. The dashboard discovery test stopped skipping once
`examples\prices.csv` existed, because that test needs a persisted discovery
report.

Commits for this session, oldest first:

| Commit | Item |
| --- | --- |
| `15f909f` | Read an un-spaced hyphen as subtraction, not a symbol name |
| `e8286d0` | Refuse a contract pair whose size and tick value do not scale together |
| `55c007c` | Do not report an unevaluated candidate as measured, and bound the family |
| `954ff1d` | Remove the cost model that no calculation used |

Test count went from 324 to 362. Each correction added regression tests that fail
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

## Environment note

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

Remaining counts: **0 High, 7 Medium, 9 Low**, plus 2 Phase 10 items that are
deliberately out of scope.

The next item, first under **Medium**:

`parallel_collection.py` — raising inside the executor drains the pool on
shutdown while workers keep writing datasets, and `DataQualityError` is retried
three times, each attempt minting a new `dataset_id` and orphaning the previous
output. This is the same class of defect as the ones just corrected — a retry
that looks like robustness while silently discarding work — and the orphaned
datasets are the kind of leftover the storage layer's atomic manifest is
supposed to prevent.

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

