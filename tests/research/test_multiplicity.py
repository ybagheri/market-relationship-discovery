"""Tests for false-discovery control across candidate relationships.

The property that matters is that a family of uncorrelated candidates produces
roughly ``alpha * tests`` false positives when read one at a time, and that the
correction removes most of them. A controller that merely echoes the per-test
verdict would pass a naive test and still mislead a researcher.
"""

from __future__ import annotations

import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests

from market_relationship_discovery.statistics.multiplicity import (
    DEFAULT_METHOD,
    FamilyHypothesis,
    MultiplicityController,
    MultiplicityMethod,
    build_family,
    stationarity_p_value,
)


def hypotheses(values: list[float]) -> tuple[FamilyHypothesis, ...]:
    return tuple(
        FamilyHypothesis(label=f"C{index:02d}", p_value=value) for index, value in enumerate(values)
    )


def test_default_method_controls_the_false_discovery_rate() -> None:
    assert DEFAULT_METHOD is MultiplicityMethod.FDR_BH


def test_correction_removes_false_positives_from_a_large_uncorrelated_family() -> None:
    """Twenty uncorrelated candidates produce about one chance rejection.

    Read individually at five percent, roughly one candidate looks significant.
    The correction must reject far fewer, which is the whole point of applying
    it to a discovered family rather than testing each candidate in isolation.
    """
    generator = np.random.default_rng(20260926)
    values = list(np.round(generator.uniform(0.0, 1.0, size=20), 6))

    report = MultiplicityController().adjust(hypotheses(values))

    assert report.tests == 20
    assert report.expected_false_positives == pytest.approx(1.0)
    assert report.unadjusted_rejections >= report.adjusted_rejections
    assert report.adjusted_rejections <= report.unadjusted_rejections


def test_adjusted_p_values_match_the_reference_implementation() -> None:
    values = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]

    report = MultiplicityController(MultiplicityMethod.FDR_BH).adjust(hypotheses(values))
    expected = multipletests(np.array(values), alpha=0.05, method="fdr_bh")[1]

    produced = {item.label: item.adjusted_p_value for item in report.hypotheses}
    for index in range(len(values)):
        assert produced[f"C{index:02d}"] == pytest.approx(float(expected[index]))


def test_a_genuine_strong_signal_survives_correction() -> None:
    """Correction must not simply reject everything."""
    values = [0.0001, *([0.9] * 19)]

    report = MultiplicityController().adjust(hypotheses(values))

    assert report.retained_after_correction >= 1
    assert report.hypotheses[0].label == "C00"
    assert report.hypotheses[0].survived_correction is True


def test_bonferroni_is_at_least_as_conservative_as_fdr() -> None:
    values = [0.01, 0.02, 0.03, 0.04, 0.05, 0.2, 0.3, 0.4, 0.5, 0.6]

    strict = MultiplicityController(MultiplicityMethod.BONFERRONI).adjust(hypotheses(values))
    loose = MultiplicityController(MultiplicityMethod.FDR_BH).adjust(hypotheses(values))

    assert strict.adjusted_rejections <= loose.adjusted_rejections


def test_every_candidate_is_reported_even_when_none_survives() -> None:
    values = [0.4, 0.5, 0.6, 0.7]

    report = MultiplicityController().adjust(hypotheses(values))

    assert len(report.hypotheses) == 4
    assert report.retained_after_correction == 0
    assert report.adjusted_rejections == 0
    assert all(item.survived_correction is False for item in report.hypotheses)


def test_hypotheses_are_ranked_by_adjusted_p_value() -> None:
    values = [0.5, 0.001, 0.2]

    report = MultiplicityController().adjust(hypotheses(values))

    adjusted = [item.adjusted_p_value for item in report.hypotheses]
    assert adjusted == sorted(adjusted)
    assert report.hypotheses[0].label == "C01"
    assert report.hypotheses[0].rank == 1


def test_empty_family_is_handled() -> None:
    report = MultiplicityController().adjust((), excluded=("C00",))

    assert report.tests == 0
    assert report.adjusted_rejections == 0
    assert report.excluded == ("C00",)
    assert report.hypotheses == ()


def test_adjusted_p_value_lookup() -> None:
    report = MultiplicityController().adjust(hypotheses([0.01, 0.5]))

    assert report.adjusted_p_value("C00") is not None
    assert report.adjusted_p_value("missing") is None


def test_only_an_available_stationarity_result_contributes_a_p_value() -> None:
    available = {
        "status": "available",
        "engle_granger_p_value": 0.01,
    }
    unavailable = {
        "status": "unavailable",
        "unavailable_reason": "constant residual series",
        "engle_granger_p_value": None,
    }

    assert stationarity_p_value(available) == pytest.approx(0.01)
    assert stationarity_p_value(unavailable) is None
    assert stationarity_p_value("not a mapping") is None
    assert stationarity_p_value({}) is None


def test_a_non_numeric_p_value_is_not_treated_as_evidence() -> None:
    assert stationarity_p_value({"status": "available", "engle_granger_p_value": "n/a"}) is None
    assert stationarity_p_value({"status": "available", "engle_granger_p_value": True}) is None
    assert stationarity_p_value({"status": "available", "engle_granger_p_value": 1.7}) is None


def test_candidates_without_a_result_are_excluded_from_the_family() -> None:
    """A test that never ran must not shrink the correction for those that did."""
    summaries = {
        "XAUEUR": {
            "cointegration_stationarity": {"status": "available", "engle_granger_p_value": 0.01}
        },
        "EURGBP": {
            "cointegration_stationarity": {"status": "unavailable", "engle_granger_p_value": None}
        },
        "EURJPY": {
            "cointegration_stationarity": {"status": "available", "engle_granger_p_value": 0.4}
        },
    }

    family, excluded = build_family(summaries)
    report = MultiplicityController().adjust(family, excluded)

    assert [item.label for item in family] == ["EURJPY", "XAUEUR"]
    assert excluded == ("EURGBP",)
    assert report.tests == 2
    assert report.excluded == ("EURGBP",)


def test_hypotheses_are_validated() -> None:
    with pytest.raises(ValueError, match="p_value"):
        FamilyHypothesis(label="C00", p_value=1.5)
    with pytest.raises(ValueError, match="p_value"):
        FamilyHypothesis(label="C00", p_value=-0.1)
    with pytest.raises(ValueError, match="label"):
        FamilyHypothesis(label="", p_value=0.5)
    with pytest.raises(ValueError, match="alpha"):
        MultiplicityController(alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        MultiplicityController(alpha=1.0)


def test_a_result_with_disagreeing_tests_is_marked_contested() -> None:
    """A verdict resting on one of two conflicting tests must say so."""
    summaries = {
        "CONTESTED": {
            "cointegration_stationarity": {
                "status": "available",
                "engle_granger_p_value": 0.001,
                "stationarity_tests_agree": False,
            }
        },
        "CLEAN": {
            "cointegration_stationarity": {
                "status": "available",
                "engle_granger_p_value": 0.002,
                "stationarity_tests_agree": True,
            }
        },
    }

    family, _ = build_family(summaries)
    report = MultiplicityController().adjust(family)

    by_label = {item.label: item for item in report.hypotheses}
    assert by_label["CONTESTED"].contested is True
    assert by_label["CLEAN"].contested is False
    assert report.contested == 1


def test_a_missing_agreement_flag_is_not_treated_as_a_disagreement() -> None:
    summaries = {
        "UNKNOWN": {
            "cointegration_stationarity": {
                "status": "available",
                "engle_granger_p_value": 0.001,
            }
        }
    }

    family, _ = build_family(summaries)
    report = MultiplicityController().adjust(family)

    assert report.hypotheses[0].contested is False
    assert report.contested == 0


def test_report_is_serializable() -> None:
    report = MultiplicityController().adjust(hypotheses([0.01, 0.6]))

    payload = report.to_dict()

    assert payload["method"] == "fdr_bh"
    assert payload["tests"] == 2
    assert payload["expected_false_positives"] == pytest.approx(0.1)
    assert len(payload["hypotheses"]) == 2
