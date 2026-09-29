# Research Methodology

## Scope

Research classifies observations into theoretical discrepancy, executable discrepancy under explicit bid/ask assumptions, statistical relationship, and cost-adjusted hypothetical edge. These classes are not interchangeable.

## Pipeline

1. Normalize source timestamps to UTC.
2. Validate duplicates, missing values, positive prices, and bid/ask invariants.
3. Align feeds within a configured tolerance and retain delay information.
4. Parse and evaluate synthetic formulas.
5. Compare actual quote with theoretical and executable synthetic intervals.
6. Apply spread-independent research cost assumptions separately.
7. Measure correlation, spread normalization, persistence, and lead/lag.
8. Compute causal rolling beta and stability diagnostics.
9. Report an OLS-residual cointegration check using an augmented Dickey-Fuller test on the residuals, corroborated by a KPSS level-stationarity test.
10. Label all output as a research candidate unless a later validation process proves more.

## Stationarity and cointegration

Cointegration is tested with a two-step Engle-Granger style procedure. The target is regressed on the benchmark, and an augmented Dickey-Fuller test with AIC lag selection is applied to the OLS residuals using `statsmodels.tsa.stattools.coint`. A KPSS level-stationarity test is run on the same residuals as corroboration, because both tests can reject and a disagreement is a meaningful result.

The step 2 p-value is the one adjusted for a single cointegrating regressor, because the residuals being tested were produced by a regression containing one. Reading the MacKinnon table for the zero-regressor case instead, as a bare `adfuller` call on the residuals does, is anti-conservative: on near unit-root pairs it reported p-values around half the correct value, and pairs whose residuals are clearly non-stationary came back significant at the 5% level. The unadjusted value is reported alongside as `adf_p_value_without_regressor_adjustment` so the size of the correction is visible rather than assumed.

Three safeguards exist because a naive implementation of this procedure reports confident false positives:

- At least 30 aligned observations are required. Below that the result is reported as `unavailable` with a reason.
- A constant, non-finite, or otherwise degenerate residual series is reported as `unavailable`. A perfect formula identity leaves no residual variation to test, and an earlier approximation returned a sentinel value that was reported as strong cointegration evidence.
- A pair that is so nearly collinear that the benchmark explains almost all of the target variance is reported as `unavailable`, naming collinearity as the reason. In that condition `coint` returns a statistic of `-inf` with a p-value of zero, which it documents as numerically unstable rather than as a test result. Reporting that zero would certify a cointegrated relationship the test never measured.

Each result reports `cointegrated_at_significance`, the ADF and KPSS conclusions, whether the two tests agree, `adf_p_value_is_regressor_adjusted`, and `kpss_p_value_is_bounded`. The KPSS lookup table bounds its p-value from below, so a bounded result is flagged rather than presented as an exact probability.

A rejected null hypothesis is evidence about the historical sample only. It is not evidence of an executable edge, and it does not survive costs by itself.

## Statistical limitations

Pearson correlation measures linear co-movement; Spearman measures rank co-movement. Neither establishes causality, cointegration, or arbitrage. Rolling z-score depends on its window and regime. Half-life is descriptive and unstable in non-stationary or sparse data. Lead/lag results can change with resampling and timestamp tolerance.

### Minimum samples

A statistic computed on a sample too small to support it reports why it is absent rather than a number. An absent figure is not a measured zero, and a value of `0.0` is indistinguishable from a real measurement of no relationship.

- **Correlation** requires at least 8 aligned observations. Any three points on a straight line correlate at exactly 1.0, so a three-observation minimum guaranteed a perfect relationship that was an artefact of the sample size, and a caller could not tell it from a measured one.
- **Half-life** requires at least 20 observations, and the regression slope must be distinguishable from zero at the 5% level. The estimate is `-ln(2) / slope` from regressing the change on the level, so a slope near zero makes it diverge; without the significance requirement a series that never reverts reported a figure like 6e15, describing the slope rather than the market.
- **Lead/lag** requires at least 8 aligned observations per lag, and reports `None` for a p-value below that rather than a value computed from a handful of points.

A bound on the *resulting* half-life — rejecting an estimate longer than the sample — was written and removed. For an AR(1) process the half-life is `ln(0.5)/ln(rho)`, which exceeds the sample length only above `rho` of about 0.999, and at that coefficient the slope is no longer distinguishable from zero in any sample of practical size. The bound could never fire while its precondition held, which would have been a check that always passes while implying the extremes were covered.

### Lead/lag conventions

A positive `lag` means the **predictor leads**: the predictor is shifted forward and compared with the target at a later instant. A negative `lag` means the predictor lags. The result carries `predictor_leads` and `predictor_lags` columns in words, because a sign convention that has to be inferred from the code is not a convention.

Every lag reports a two-sided p-value and a `significant_and_usable` flag, which requires both significance and an effect size of at least 0.2 in absolute correlation. The raw correlation is always published, so a reader deciding for themselves does not have to reconstruct it, and a strong-looking correlation from four observations stays visible rather than hidden.

A correlation is not causation and a lead/lag maximum is not a tradable signal. It describes the historical sample under the chosen lag convention and alignment.


The cointegration, ADF, and KPSS outputs are retrospective full-sample diagnostics. They do not establish causality, execution, future returns, or multiple-testing-adjusted significance. Advanced research also supports causal volatility regimes, dependency-graph expansion, and deterministic chronological ridge ranking over bar-price panels.

## Data requirements

Tick data is preferred for cross-broker executable research. Bar data supports slower relationship research but cannot establish a tick-level opportunity. Broker symbol specifications, sessions, timestamps, and feed aggregation must be recorded.
