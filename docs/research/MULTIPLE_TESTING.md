# Multiple Testing and Discovery

## Why a family of candidates needs a correction

Discovery generates many candidate relationships and reports a significance
verdict for each one independently. Reading those verdicts one at a time
overstates the evidence.

At a five percent significance level, twenty independent candidates produce
roughly **one** rejection purely by chance. Increasing graph depth adds
candidates, not evidence. A candidate that looks significant may simply be one
of the expected false positives.

The platform therefore applies a correction across the whole family and reports
how many rejections were expected under the null, so a surviving candidate is
read against the family it was drawn from.

## What is corrected

The family is the set of candidate stationarity tests produced by the advanced
discovery run. For each candidate with a usable augmented Dickey-Fuller result,
the reported `engle_granger_p_value` becomes one member of the family.

Candidates whose stationarity test never ran are **excluded** and listed
separately. An absent result is not evidence. Including a missing result as a
large p-value would suppress the correction for the candidates that did run, so
exclusion is the conservative choice.

## Methods

| Method | Controls | When to use it |
| --- | --- | --- |
| `fdr_bh` | Expected proportion of false discoveries | Default; discovery here is exploratory |
| `fdr_by` | Expected proportion, more conservative | When a few true findings matter more than power |
| `bonferroni` | Family-wise error rate | Strictest; fewest rejections |
| `holm` | Family-wise error rate | Strict but more powerful than Bonferroni |
| `sidak` | Family-wise error rate | Assumes independence |

The default is `fdr_bh`. Select another with:

```bash
python -m market_relationship_discovery discover --input prices.csv --multiplicity-method bonferroni
```

The procedures are delegated to `statsmodels.stats.multitest.multipletests`
rather than reimplemented. Hand-rolled statistics are what produced the
degenerate cointegration result this project had to correct earlier, so the
correction uses a tested implementation and the test suite checks its adjusted
p-values against that reference directly.

## Reading the output

The `multiplicity` block of an advanced discovery report contains:

| Field | Meaning |
| --- | --- |
| `method` | Correction applied |
| `alpha` | Significance level used |
| `tests` | Candidates that actually ran a test |
| `excluded` | Candidates with no usable result |
| `expected_false_positives` | `tests × alpha`, the chance rejections expected |
| `unadjusted_rejections` | Candidates that looked significant read individually |
| `adjusted_rejections` | Candidates that survive the correction |
| `retained_after_correction` | Count surviving, and significant before correction |
| `contested` | Candidates whose ADF and KPSS verdicts disagreed |
| `hypotheses` | Per-candidate raw and adjusted p-value, verdict, rank, and contested flag |

A candidate is reported as `survived_correction` only when it is both rejected
by the procedure and individually significant. The distinction matters: a
candidate can pass the procedure while being individually weak.

Comparing `unadjusted_rejections` with `adjusted_rejections` shows how much of
the apparent discovery was chance.

### Contested results

The family is keyed on the augmented Dickey-Fuller p-value. When the KPSS test
contradicts it, the verdict rests on one of two conflicting tests, so the
candidate is marked `contested`.

This is not a formality. On real data `EURGBP_SYNTHETIC` survived correction with
an adjusted p-value of 0.0013 while its two stationarity tests disagreed.
Reported as a single number it read as a clean result; reported as surviving and
contested it reads correctly.

## What a correction does not do

A correction controls false discoveries. It does not make anything tradable.

A candidate that survives multiplicity correction still has to pass the separate
gates: costs, contract compatibility, and execution feasibility. The
cross-broker layer applies those independently, and a shared ticker across two
brokers with a ten times tick-value difference fails the contract gate no matter
how significant its statistics are.

Neither does a correction repair a badly chosen family. Testing correlated
duplicates of the same relationship inflates the family without adding
information, and corrections such as `sidak` assume independence that price
series do not satisfy. `holm` and `bonferroni` remain valid under dependence,
which is the safer choice when candidates overlap.

## Observed run

Against 1370 M1 bars from one demo broker covering six symbols, the discovery
graph produced two testable candidates:

| Candidate | Raw p | Adjusted p | Survived |
| --- | --- | --- | --- |
| `EURGBP_SYNTHETIC` | 0.00067 | 0.00134 | yes |
| `XAUEUR_SYNTHETIC` | 0.05621 | 0.05621 | no |

`expected_false_positives` was 0.1 for a family of two. The EURGBP result is
strong enough to survive comfortably. The XAUEUR relationship sits just outside
the threshold and is reported as not surviving rather than being presented as a
marginal discovery.

The same relationship gave a different answer on a shorter sample. At 300 bars
`XAUEUR` produced an adjusted Dickey-Fuller p-value of 0.61, and at 1500 bars the
EURGBP relationship produced 0.0007 where the shorter run had produced 0.61.
Stationarity verdicts are sample dependent, which is a further reason not to
read a single run as a discovery.
