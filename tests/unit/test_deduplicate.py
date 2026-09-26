"""Tests for candidate-family de-duplication.

The point of the module is that two candidates asserting the same hypothesis are
one test, not two. A duplicate inflates the family, which makes a
false-discovery correction stricter for no reason and makes the reported family
size misleading.
"""

from __future__ import annotations

import pytest

from market_relationship_discovery.discovery.deduplicate import (
    CandidateDeduplicator,
    CandidateFingerprint,
    NormalizationError,
    canonical_formula,
)
from market_relationship_discovery.discovery.engine import CandidateStatus, DiscoveryCandidate
from market_relationship_discovery.relationships.formula import FormulaParser


def candidate(name: str, target: str, formula: str) -> DiscoveryCandidate:
    return DiscoveryCandidate(name, target, formula, CandidateStatus.RESEARCH_CANDIDATE)


def test_renaming_a_relationship_does_not_create_a_second_test() -> None:
    """The same target and formula under two names is one hypothesis."""
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("XAUEUR_SYNTHETIC", "XAUEUR", "XAUUSD / EURUSD"),
            candidate("GOLD_EUR", "XAUEUR", "XAUUSD / EURUSD"),
        ]
    )

    assert [item.name for item in report.kept] == ["XAUEUR_SYNTHETIC"]
    assert report.duplicates == (("XAUEUR_SYNTHETIC", "GOLD_EUR"),)
    assert report.removed_count == 1
    assert report.input_count == 2


def test_whitespace_variants_collapse() -> None:
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("A", "T", "A * B"),
            candidate("B", "T", "A*B"),
        ]
    )

    assert len(report.kept) == 1


def test_commutative_regrouping_collapses() -> None:
    """``A * B * C`` and ``C * A * B`` assert the same value."""
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("A", "T", "A * B * C"),
            candidate("B", "T", "C * B * A"),
        ]
    )

    assert len(report.kept) == 1


def test_redundant_parentheses_collapse() -> None:
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("A", "T", "A / (B * C)"),
            candidate("B", "T", "A / (B * C)"),
        ]
    )

    assert len(report.kept) == 1


def test_different_formulas_for_one_target_remain_separate_tests() -> None:
    """Two ways to reach a target are two hypotheses, not a duplicate."""
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("DIRECT", "EURJPY", "EURUSD * USDJPY"),
            candidate("VIA_GBP", "EURJPY", "EURGBP * GBPJPY"),
        ]
    )

    assert len(report.kept) == 2
    assert report.removed_count == 0


def test_inverted_ratios_are_not_collapsed() -> None:
    """``A / B`` and ``B / A`` are different claims."""
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("FORWARD", "RATIO", "EURUSD / GBPUSD"),
            candidate("INVERSE", "RATIO", "GBPUSD / EURUSD"),
        ]
    )

    assert len(report.kept) == 2


def test_the_first_occurrence_is_kept_so_ordering_stays_stable() -> None:
    deduplicator = CandidateDeduplicator()
    candidates = [
        candidate("FIRST", "T", "A / B"),
        candidate("SECOND", "T", "A / B"),
        candidate("THIRD", "T", "A / B"),
    ]

    report = deduplicator.deduplicate(candidates)

    assert [item.name for item in report.kept] == ["FIRST"]
    assert report.duplicates == (("FIRST", "SECOND"), ("FIRST", "THIRD"))


def test_candidates_with_an_unparsable_formula_are_reported_not_silently_dropped() -> None:
    deduplicator = CandidateDeduplicator()

    report = deduplicator.deduplicate(
        [
            candidate("GOOD", "T", "A / B"),
            candidate("BROKEN", "T", "A /"),
        ]
    )

    assert [item.name for item in report.kept] == ["GOOD"]
    assert report.unparsable == ("BROKEN",)
    assert report.input_count == 2


def test_canonical_formula_is_stable_for_equivalent_expressions() -> None:
    first = canonical_formula(FormulaParser.parse("A * B * C"))
    second = canonical_formula(FormulaParser.parse("C * A * B"))
    third = canonical_formula(FormulaParser.parse("A*(B*C)"))

    assert first == second == third


def test_canonical_formula_preserves_division_order() -> None:
    first = canonical_formula(FormulaParser.parse("A / B"))
    second = canonical_formula(FormulaParser.parse("B / A"))

    assert first != second


def test_fingerprint_records_dependencies() -> None:
    fingerprint = CandidateFingerprint.of(candidate("A", "T", "XAUUSD / EURUSD"))

    assert fingerprint.target == "T"
    assert fingerprint.dependencies == ("EURUSD", "XAUUSD")
    assert "T" in fingerprint.describe()


def test_fingerprint_rejects_an_unusable_formula() -> None:
    with pytest.raises(NormalizationError, match="unusable formula"):
        CandidateFingerprint.of(candidate("BROKEN", "T", "A +"))


def test_report_is_serializable() -> None:
    deduplicator = CandidateDeduplicator()

    payload = deduplicator.deduplicate(
        [
            candidate("KEEP", "T", "A / B"),
            candidate("DROP", "T", "A / B"),
        ]
    ).to_dict()

    assert payload["input_candidates"] == 2
    assert payload["kept_candidates"] == 1
    assert payload["removed_duplicates"] == [{"kept": "KEEP", "removed": "DROP"}]
    assert payload["unparsable_formulas"] == []


def test_deduplication_never_mutates_its_input() -> None:
    deduplicator = CandidateDeduplicator()
    candidates = [
        candidate("A", "T", "A / B"),
        candidate("B", "T", "A / B"),
    ]

    deduplicator.deduplicate(candidates)

    assert [item.name for item in candidates] == ["A", "B"]
