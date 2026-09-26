# Panel Coverage and Candidate Families

## Why coverage must be reported

A price panel collected in one broker request can look complete while being
useless. `collect --limit 1500` returns the last 1500 bars **per symbol**, and a
symbol with thin liquidity or a stale history reaches much further back in
calendar time than a liquid one.

Observed on a real Alpari demo account, one request for nine M1 symbols produced:

| Symbol | Last bar | Gap before the union window end |
| --- | --- | --- |
| `EURUSD`, `EURGBP`, `EURJPY` | 2026-09-25 23:54 | none |
| `XAUEUR`, `XAUUSD` | 2026-09-25 23:54 | none |
| `XAGUSD` | 2026-09-23 15:17 | 2 days |
| `GBPJPY` | 2026-09-24 14:18 | 1 day |
| `USDJPY` | 2026-09-09 12:34 | 16 days |

The union held 5911 timestamps and **zero** were shared by every symbol. Any
`dropna` across all nine columns returned an empty frame, and the failure
surfaced far from its cause as `prices must be finite positive values` from a
statistics routine. That message says nothing about the misalignment that
produced it, and a reader has no way to guess that the panel was the problem.

Coverage is now measured and reported before any relationship is tested.

## What is reported

The `coverage` block of an advanced discovery report contains, per symbol:
observation count, first and last timestamp, coverage fraction of the union
window, and largest gap. It also reports:

| Field | Meaning |
| --- | --- |
| `union_rows` | Distinct timestamps across all supplied symbols |
| `fully_overlapping_rows` | Timestamps present in **every** symbol |
| `best_shared_window` | Largest contiguous window a comparable set shares |
| `analysed_symbols` | Symbols actually used |
| `analysed_rows` | Rows in the analysed sub-panel |
| `excluded_symbols` | Symbols dropped, by name |
| `issues` | Human-readable findings |

The analysis is restricted to the largest shared window and every excluded
symbol is named. Nothing is filled, interpolated, or widened to manufacture
overlap.

## Choosing the shared window

Finding the window is not a simple intersection, because a daily session break
means no symbol is present on every bar of a multi-day window.

The analyzer first locates the longest run where at least the minimum number of
symbols are present. Symbols spanning that run entirely are preferred. When none
do, a greedy pass repeatedly adds whichever symbol maximises the shared window.

Choosing symbols by column order instead would be wrong. In the real panel
above, alphabetical order pairs `GBPJPY` with `EURGBP`, and those two never trade
at the same time, so the pair has no overlap at all. The greedy pass instead
selects `EURGBP` and `EURJPY`, which share 1500 consecutive rows.

## When no window exists

`require_usable` fails with a message naming the problem, the affected symbols,
and the remedy. The previous behaviour was an unrelated statistics error.

## Candidate de-duplication

Testing one hypothesis twice inflates the family. That makes a false-discovery
correction stricter for no reason and makes the reported family size misleading,
because a reader counts candidates rather than distinct hypotheses.

The relationship graph already removed definitions identical in name, target,
and formula. That is not sufficient. Two candidates can assert the same
hypothesis while differing in ways a reader would not notice:

- a different relationship **name** for the same target and formula,
- a different **spelling**, such as `A * B` and `A*B`,
- a different **grouping** that evaluates identically, such as `A / (B * C)` and
  `A / B / C`.

Candidates are keyed on the target plus a canonical rendering of the formula,
produced by the existing `FormulaParser`.

### Associativity has to be flattened

Multiplication and addition are both associative and commutative, so their chains
are flattened into a sorted multiset before being rebuilt. Sorting each pair in
isolation is not sufficient: `A * B * C` parses as `((A*B)*C)` while
`C * A * B` parses as `((C*A)*B)`, and no pairwise ordering makes those two trees
agree.

Division and subtraction are neither associative nor commutative, so their
operand order is preserved exactly. `A / B` and `B / A` assert different things
and must remain separate hypotheses.

### What is deliberately not merged

Two different formulas reaching the same target are two hypotheses:

```text
EURJPY = EURUSD * USDJPY
EURJPY = EURGBP * GBPJPY
```

These are separate tests and both are kept. Merging them would discard evidence,
not deduplicate it.

The first occurrence is kept so discovery order stays stable and the catalog's
own naming wins, which keeps reports readable. Collapsed and unparsable candidate
names are reported rather than dropped silently.

## Contested results

The false-discovery family is keyed on the augmented Dickey-Fuller p-value. When
the KPSS test contradicts it, the verdict rests on one of two conflicting tests,
so the candidate is marked `contested` and counted separately in the report.

Observed on real data: `EURGBP_SYNTHETIC` survived correction with an adjusted
p-value of 0.0013, but its two stationarity tests disagreed, so it is reported as
surviving **and** contested. A reader who saw only the adjusted p-value would
have read a contested result as a clean one.

## Limitations

- Coverage describes presence in time, not data quality. A symbol can cover the
  window and still be stale, gappy, or wrong; the per-dataset quality report
  covers that separately.
- A session break means coverage rarely reaches 100 percent for a multi-day
  window, so `fully_overlapping_rows` is not the measure of usability. The
  shared window is.
- The greedy subset search is not exhaustive. It is quadratic in symbol count and
  maximises the shared window, but with many candidates a different subset could
  in principle be marginally better.
- De-duplication compares formulas, not semantics. Two formulas that are
  algebraically equal in a way the parser does not normalise, such as
  `(A/B)*B` against `A`, are still separate candidates.
