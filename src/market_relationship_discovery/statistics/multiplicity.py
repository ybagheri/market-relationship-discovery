"""False-discovery control across a family of candidate relationships.

Discovery evaluates many candidate relationships and reports a significance
verdict for each one independently. That is the wrong way to read the result.
At a five percent level, twenty independent candidates produce roughly one
false positive purely by chance, and a deeper graph expansion produces more
candidates, not better evidence.

This module applies a correction across the whole family and reports how many
rejections were expected under the null, so a surviving candidate is presented
as a research candidate that survived false-discovery control rather than as a
discovery in isolation.

The corrections are delegated to :func:`statsmodels.stats.multitest.multipletests`
rather than reimplemented. Hand-rolled statistics are what produced the
degenerate cointegration result this project had to correct earlier.

A correction controls false discoveries. It says nothing about tradability, and
a surviving candidate still has to survive costs, contract compatibility, and
execution feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from statsmodels.stats.multitest import multipletests


class MultiplicityMethod(StrEnum):
    """Supported false-discovery control procedures.

    ``FDR_BH`` controls the expected proportion of false discoveries and is the
    default because discovery here is exploratory. ``FDR_BY`` is more
    conservative and appropriate when a small number of true findings matters
    more than power. ``BONFERRONI`` and ``HOLM`` control the family-wise error
    rate, which is the strictest option.
    """

    BONFERRONI = "bonferroni"
    HOLM = "holm"
    SIDAK = "sidak"
    FDR_BH = "fdr_bh"
    FDR_BY = "fdr_by"


DEFAULT_METHOD = MultiplicityMethod.FDR_BH


@dataclass(frozen=True, slots=True)
class FamilyHypothesis:
    """One candidate's test result entering the family."""

    label: str
    p_value: float
    tests_agree: bool | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.p_value <= 1.0:
            raise ValueError("p_value must lie between zero and one")
        if not self.label:
            raise ValueError("label is required")

    @property
    def is_contested(self) -> bool:
        """Whether the corroborating stationarity test contradicted the primary one.

        The family is keyed on the augmented Dickey-Fuller p-value. When the
        KPSS test disagrees, the verdict rests on one of two conflicting tests,
        and a reader should see that rather than a single clean number.
        """
        return self.tests_agree is False


@dataclass(frozen=True, slots=True)
class AdjustedHypothesis:
    label: str
    raw_p_value: float
    adjusted_p_value: float
    rejected: bool
    unadjusted_rejected: bool
    survived_correction: bool
    rank: int
    contested: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "raw_p_value": self.raw_p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "rejected": self.rejected,
            "unadjusted_rejected": self.unadjusted_rejected,
            "survived_correction": self.survived_correction,
            "rank": self.rank,
            "contested": self.contested,
        }


@dataclass(frozen=True, slots=True)
class MultiplicityReport:
    """Outcome of false-discovery control over a family of tests."""

    method: str
    alpha: float
    tests: int
    excluded: tuple[str, ...]
    expected_false_positives: float
    unadjusted_rejections: int
    adjusted_rejections: int
    retained_after_correction: int
    contested: int
    hypotheses: tuple[AdjustedHypothesis, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "alpha": self.alpha,
            "tests": self.tests,
            "excluded": list(self.excluded),
            "expected_false_positives": self.expected_false_positives,
            "unadjusted_rejections": self.unadjusted_rejections,
            "adjusted_rejections": self.adjusted_rejections,
            "retained_after_correction": self.retained_after_correction,
            "contested": self.contested,
            "hypotheses": [item.to_dict() for item in self.hypotheses],
        }

    def adjusted_p_value(self, label: str) -> float | None:
        for item in self.hypotheses:
            if item.label == label:
                return item.adjusted_p_value
        return None


class MultiplicityController:
    """Apply false-discovery control to a family of candidate tests."""

    def __init__(
        self,
        method: MultiplicityMethod = DEFAULT_METHOD,
        alpha: float = 0.05,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must lie strictly between zero and one")
        self._method = method
        self._alpha = alpha

    def adjust(
        self,
        hypotheses: tuple[FamilyHypothesis, ...],
        excluded: tuple[str, ...] = (),
    ) -> MultiplicityReport:
        """Adjust a family of p-values.

        Candidates without a usable p-value are listed as ``excluded`` and left
        out of the family size, because a test that never ran cannot inflate or
        deflate the correction.
        """
        tests = len(hypotheses)
        if tests == 0:
            return MultiplicityReport(
                method=self._method.value,
                alpha=self._alpha,
                tests=0,
                excluded=tuple(excluded),
                expected_false_positives=0.0,
                unadjusted_rejections=0,
                adjusted_rejections=0,
                retained_after_correction=0,
                contested=0,
                hypotheses=(),
            )
        values = np.array([item.p_value for item in hypotheses], dtype=float)
        rejected, adjusted = multipletests(
            values,
            alpha=self._alpha,
            method=self._method.value,
        )[:2]
        order = np.argsort(values, kind="stable")
        ranks = np.empty(tests, dtype=int)
        ranks[order] = np.arange(1, tests + 1)
        unadjusted_rejected = int((values < self._alpha).sum())
        results: list[AdjustedHypothesis] = []
        for index, hypothesis in enumerate(hypotheses):
            survived = bool(rejected[index]) and bool(values[index] < self._alpha)
            results.append(
                AdjustedHypothesis(
                    label=hypothesis.label,
                    raw_p_value=float(values[index]),
                    adjusted_p_value=float(adjusted[index]),
                    rejected=bool(rejected[index]),
                    unadjusted_rejected=bool(values[index] < self._alpha),
                    survived_correction=survived,
                    rank=int(ranks[index]),
                    contested=hypothesis.is_contested,
                )
            )
        results.sort(key=lambda item: (item.adjusted_p_value, item.rank))
        return MultiplicityReport(
            method=self._method.value,
            alpha=self._alpha,
            tests=tests,
            excluded=tuple(excluded),
            expected_false_positives=tests * self._alpha,
            unadjusted_rejections=unadjusted_rejected,
            adjusted_rejections=int(rejected.sum()),
            retained_after_correction=sum(1 for item in results if item.survived_correction),
            contested=sum(1 for item in results if item.contested),
            hypotheses=tuple(results),
        )


def stationarity_p_value(summary: object) -> float | None:
    """Extract a usable p-value from a stationarity result block.

    Only an available augmented Dickey-Fuller result contributes. A degenerate
    or too-short residual series is not evidence of anything and must not enter
    the family, because treating an absent result as a large p-value would
    quietly suppress the correction for the candidates that did run.
    """
    if not isinstance(summary, dict):
        return None
    if summary.get("status") != "available":
        return None
    value = summary.get("engle_granger_p_value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0.0 <= float(value) <= 1.0:
        return None
    return float(value)


def stationarity_agreement(summary: object) -> bool | None:
    """Return whether the ADF and KPSS verdicts agreed, when that is known."""
    if not isinstance(summary, dict) or summary.get("status") != "available":
        return None
    value = summary.get("stationarity_tests_agree")
    if isinstance(value, bool):
        return value
    return None


def build_family(
    summaries: dict[str, object],
) -> tuple[tuple[FamilyHypothesis, ...], tuple[str, ...]]:
    """Collect candidate stationarity results into a testable family.

    Returns the usable hypotheses and the labels excluded for lacking a result.
    """
    hypotheses: list[FamilyHypothesis] = []
    excluded: list[str] = []
    for label in sorted(summaries):
        block = summaries[label]
        nested = block.get("cointegration_stationarity") if isinstance(block, dict) else None
        p_value = stationarity_p_value(nested)
        if p_value is None:
            excluded.append(label)
            continue
        hypotheses.append(
            FamilyHypothesis(
                label=label,
                p_value=p_value,
                tests_agree=stationarity_agreement(nested),
            )
        )
    return tuple(hypotheses), tuple(excluded)
