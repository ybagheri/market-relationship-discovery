from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import permutations

from market_relationship_discovery.relationships.catalog import RelationshipDefinition


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


class CandidateDiscoveryEngine:
    def generate(
        self, symbols: Sequence[str], minimum_observations: int = 100
    ) -> list[DiscoveryCandidate]:
        unique_symbols = sorted(set(symbols))
        candidates: list[DiscoveryCandidate] = []
        for numerator, denominator in permutations(unique_symbols, 2):
            target = f"SYNTH_{numerator}_DIV_{denominator}"
            candidates.append(
                DiscoveryCandidate(
                    name=f"{target}_RATIO",
                    target=target,
                    formula=f"{numerator} / {denominator}",
                    status=CandidateStatus.REQUIRES_DATA,
                )
            )
        for first, second, third in permutations(unique_symbols, 3):
            target = f"SYNTH_{first}_{second}_DIV_{third}"
            candidates.append(
                DiscoveryCandidate(
                    name=f"{target}_SYNTHETIC",
                    target=target,
                    formula=f"{first} * {second} / {third}",
                    status=CandidateStatus.REQUIRES_DATA,
                )
            )
        return self.filter(candidates, minimum_observations=minimum_observations)

    @staticmethod
    def filter(
        candidates: Sequence[DiscoveryCandidate],
        minimum_observations: int,
    ) -> list[DiscoveryCandidate]:
        return [
            (
                candidate
                if candidate.observations >= minimum_observations
                else DiscoveryCandidate(
                    name=candidate.name,
                    target=candidate.target,
                    formula=candidate.formula,
                    status=CandidateStatus.INSUFFICIENT_OBSERVATIONS,
                    observations=candidate.observations,
                    metrics=candidate.metrics,
                )
            )
            for candidate in candidates
        ]

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
