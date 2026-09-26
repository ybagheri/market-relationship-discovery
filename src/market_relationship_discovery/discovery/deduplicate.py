"""Collapse duplicate candidates before they enter a statistical family.

Testing the same relationship twice inflates the candidate family without adding
information, and an inflated family makes a false-discovery correction stricter
for no reason. Worse, it makes the reported family size misleading, because a
reader counts candidates rather than distinct hypotheses.

The relationship graph already removes definitions that are identical in name,
target, and formula. That is not enough. Two candidates can describe the same
hypothesis while differing in ways a reader would not notice:

- a different relationship *name* for the same target and formula,
- a different *spelling* of the same formula, such as ``A * B`` and ``A*B``,
- a different *grouping* that evaluates identically, such as ``A / (B * C)``
  and ``A / B / C``.

This module normalises a formula through the existing
:class:`FormulaParser` and keys candidates on the target plus that canonical
form. It never merges candidates that differ in what they actually assert: two
different formulas for the same target remain separate hypotheses, because they
are separate tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from market_relationship_discovery.discovery.engine import DiscoveryCandidate
from market_relationship_discovery.relationships.formula import Expression, FormulaParser, Operation


class NormalizationError(ValueError):
    """Raised when a candidate formula cannot be canonicalised."""


def canonical_formula(expression: Expression) -> str:
    """Render an expression in a canonical, comparable form.

    Multiplication and addition are associative as well as commutative, so their
    chains are flattened into a sorted multiset before being rebuilt. Sorting
    each pair in isolation is not enough: ``A * B * C`` parses as ``((A*B)*C)``
    while ``C * A * B`` parses as ``((C*A)*B)``, and no pairwise ordering makes
    those two trees agree.

    Division and subtraction are neither associative nor commutative, so their
    operand order is preserved exactly. Parentheses are emitted only where
    precedence requires them, which removes redundant grouping.
    """
    if expression.symbol is not None:
        return expression.symbol
    if expression.left is None or expression.right is None:
        raise NormalizationError("invalid expression node")
    operation = expression.operation
    if operation is None:
        raise NormalizationError("expression node has no operation")
    if operation in {Operation.MULTIPLY, Operation.ADD}:
        separator = "*" if operation is Operation.MULTIPLY else "+"
        factors = sorted(_flatten(expression, operation))
        return "(" + separator.join(factors) + ")"
    left = canonical_formula(expression.left)
    right = canonical_formula(expression.right)
    if operation is Operation.DIVIDE:
        return f"({left}/{right})"
    if operation is Operation.SUBTRACT:
        return f"({left}-{right})"
    raise NormalizationError(f"unsupported operation: {operation}")


def _flatten(expression: Expression, operation: Operation) -> list[str]:
    """Collect the canonical operands of an associative chain."""
    if expression.symbol is not None:
        return [expression.symbol]
    if expression.left is None or expression.right is None:
        raise NormalizationError("invalid expression node")
    if expression.operation is operation:
        return _flatten(expression.left, operation) + _flatten(expression.right, operation)
    return [canonical_formula(expression)]


@dataclass(frozen=True, slots=True)
class CandidateFingerprint:
    """Identity of the hypothesis a candidate asserts."""

    target: str
    canonical: str
    dependencies: tuple[str, ...]

    @classmethod
    def of(cls, candidate: DiscoveryCandidate) -> CandidateFingerprint:
        try:
            expression = FormulaParser.parse(candidate.formula)
            canonical = canonical_formula(expression)
            dependencies = tuple(sorted(expression.dependencies()))
        except ValueError as exc:
            raise NormalizationError(
                f"candidate {candidate.name!r} has an unusable formula "
                f"{candidate.formula!r}: {exc}"
            ) from exc
        return cls(
            target=candidate.target.strip().upper(),
            canonical=canonical,
            dependencies=dependencies,
        )

    def describe(self) -> str:
        return f"{self.target} = {self.canonical}"


@dataclass(frozen=True, slots=True)
class DeduplicationReport:
    """What de-duplication removed and what it kept."""

    kept: tuple[DiscoveryCandidate, ...]
    duplicates: tuple[tuple[str, str], ...]
    unparsable: tuple[str, ...]

    @property
    def removed_count(self) -> int:
        return len(self.duplicates)

    @property
    def input_count(self) -> int:
        return len(self.kept) + len(self.duplicates) + len(self.unparsable)

    def to_dict(self) -> dict[str, object]:
        return {
            "input_candidates": self.input_count,
            "kept_candidates": len(self.kept),
            "removed_duplicates": [
                {"kept": kept, "removed": removed} for kept, removed in self.duplicates
            ],
            "unparsable_formulas": list(self.unparsable),
        }


class CandidateDeduplicator:
    """Keep one representative per distinct hypothesis.

    The first occurrence is kept so that discovery order stays stable and the
    catalog's own naming wins, which keeps reports readable. Collapsed names are
    reported rather than dropped silently, because a reader comparing two runs
    needs to know why a candidate disappeared.
    """

    def deduplicate(
        self,
        candidates: list[DiscoveryCandidate],
    ) -> DeduplicationReport:
        kept: list[DiscoveryCandidate] = []
        duplicates: list[tuple[str, str]] = []
        unparsable: list[str] = []
        seen: dict[CandidateFingerprint, DiscoveryCandidate] = {}
        for candidate in candidates:
            try:
                fingerprint = CandidateFingerprint.of(candidate)
            except NormalizationError:
                unparsable.append(candidate.name)
                continue
            existing = seen.get(fingerprint)
            if existing is None:
                seen[fingerprint] = candidate
                kept.append(candidate)
            else:
                duplicates.append((existing.name, candidate.name))
        return DeduplicationReport(
            kept=tuple(kept),
            duplicates=tuple(duplicates),
            unparsable=tuple(unparsable),
        )

    def fingerprints(
        self,
        candidates: list[DiscoveryCandidate],
    ) -> tuple[CandidateFingerprint, ...]:
        """Fingerprint every candidate, for reporting and test assertions."""
        results: list[CandidateFingerprint] = []
        for candidate in candidates:
            results.append(CandidateFingerprint.of(candidate))
        return tuple(results)
