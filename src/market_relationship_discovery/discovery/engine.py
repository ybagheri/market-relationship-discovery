from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import permutations

from market_relationship_discovery.relationships.catalog import RelationshipDefinition
from market_relationship_discovery.relationships.formula import render_symbol

# Default bound on a generated candidate family. A three-symbol family grows as
# n(n-1)(n-2), so 40 symbols already produce 59,280 candidates; every one of them
# would otherwise enter the multiple-testing family.
DEFAULT_MAXIMUM_CANDIDATES = 500


class CandidateStatus(StrEnum):
    RESEARCH_CANDIDATE = "research_candidate"
    REQUIRES_DATA = "requires_data"
    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"
    REQUIRES_FURTHER_VALIDATION = "requires_further_validation"


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    name: str
    target: str
    formula: str
    status: CandidateStatus
    observations: int = 0
    metrics: dict[str, float] | None = None
    target_is_synthetic: bool = False


@dataclass(frozen=True, slots=True)
class CandidateFamily:
    """A generated candidate family, with what was dropped to keep it bounded.

    The family size is not a detail. Every candidate that reaches a
    multiple-testing correction widens the false-discovery rate, so an
    unbounded combinatorial family both costs time and makes the correction
    stricter for no reason. The bound and the number of candidates it removed are
    reported rather than applied silently.
    """

    candidates: tuple[DiscoveryCandidate, ...]
    generated: int

    @property
    def removed_count(self) -> int:
        """Candidates the bound removed, so a truncated family is visible."""
        return self.generated - len(self.candidates)

    @property
    def is_truncated(self) -> bool:
        return self.removed_count > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "candidates": len(self.candidates),
            "generated_candidates": self.generated,
            "removed_by_family_bound": self.removed_count,
            "family_truncated": self.is_truncated,
        }


class CandidateDiscoveryEngine:
    def generate(
        self,
        symbols: Sequence[str],
        minimum_observations: int = 100,
        maximum_candidates: int = DEFAULT_MAXIMUM_CANDIDATES,
    ) -> CandidateFamily:
        """Propose a bounded family of ratio and triple relationships.

        The two-symbol family is O(n²) and the three-symbol family is O(n³), so
        an unbounded run over a wide catalog produces a family large enough to be
        a research finding in itself: every added candidate makes the
        false-discovery correction stricter without adding evidence. The family is
        therefore bounded, and the bound is reported in :meth:`to_dict` rather
        than applied silently. Truncation keeps candidates in generated order, so
        it is deterministic for a given input.
        """
        if maximum_candidates < 1:
            raise ValueError("maximum_candidates must be at least one")
        unique_symbols = sorted(set(symbols))
        candidates: list[DiscoveryCandidate] = []
        for numerator, denominator in permutations(unique_symbols, 2):
            target = f"SYNTH_{numerator}_DIV_{denominator}"
            candidates.append(
                DiscoveryCandidate(
                    name=f"{target}_RATIO",
                    target=target,
                    # Broker names reach this f-string verbatim, and some brokers
                    # publish a hyphenated name such as ``XAU-USD``. Writing that
                    # name bare would read as a subtraction, so it is rendered
                    # such that re-parsing recovers the same symbol.
                    formula=f"{render_symbol(numerator)} / {render_symbol(denominator)}",
                    status=CandidateStatus.REQUIRES_DATA,
                    target_is_synthetic=True,
                )
            )
        for first, second, third in permutations(unique_symbols, 3):
            target = f"SYNTH_{first}_{second}_DIV_{third}"
            candidates.append(
                DiscoveryCandidate(
                    name=f"{target}_SYNTHETIC",
                    target=target,
                    formula=(
                        f"{render_symbol(first)} * {render_symbol(second)}"
                        f" / {render_symbol(third)}"
                    ),
                    status=CandidateStatus.REQUIRES_DATA,
                    target_is_synthetic=True,
                )
            )
        requested = len(candidates)
        bounded = candidates[:maximum_candidates]
        return CandidateFamily(
            candidates=tuple(
                self.filter(candidate, minimum_observations=minimum_observations)
                for candidate in bounded
            ),
            generated=requested,
        )

    @staticmethod
    def filter(
        candidate: DiscoveryCandidate,
        minimum_observations: int,
    ) -> DiscoveryCandidate:
        """Apply the observation gate without inventing a measurement.

        ``INSUFFICIENT_OBSERVATIONS`` is a claim that a candidate *was* evaluated
        and the panel held too few rows. Applying it to a candidate that was never
        evaluated reports an absent measurement as a measured one, and relabels a
        candidate awaiting data as a candidate judged on it. A candidate that
        carries no evaluation keeps its own status, so ``requires_data`` means
        "not evaluated" rather than "evaluated and found wanting".
        """
        if candidate.status is CandidateStatus.REQUIRES_DATA:
            return candidate
        if candidate.observations >= minimum_observations:
            return candidate
        return replace(
            candidate,
            status=CandidateStatus.INSUFFICIENT_OBSERVATIONS,
        )

    @staticmethod
    def catalog_to_candidates(
        definitions: Sequence[RelationshipDefinition],
    ) -> list[DiscoveryCandidate]:
        return [
            DiscoveryCandidate(
                name=definition.name,
                target=definition.target,
                formula=definition.formula,
                status=CandidateStatus.RESEARCH_CANDIDATE,
            )
            for definition in definitions
        ]
