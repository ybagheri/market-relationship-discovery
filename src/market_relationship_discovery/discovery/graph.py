from __future__ import annotations

from collections.abc import Sequence

from market_relationship_discovery.discovery.engine import (
    CandidateDiscoveryEngine,
    DiscoveryCandidate,
)
from market_relationship_discovery.relationships.catalog import INITIAL_RELATIONSHIPS
from market_relationship_discovery.relationships.graph import RelationshipGraph


class GraphRelationshipDiscoveryEngine:
    def __init__(self, graph: RelationshipGraph | None = None, *, max_depth: int = 1) -> None:
        self._graph = graph or RelationshipGraph.from_definitions(INITIAL_RELATIONSHIPS)
        self._max_depth = max_depth

    def discover(self, symbols: Sequence[str]) -> list[DiscoveryCandidate]:
        definitions = self._graph.expand(symbols, max_depth=self._max_depth)
        return CandidateDiscoveryEngine.catalog_to_candidates(definitions)
