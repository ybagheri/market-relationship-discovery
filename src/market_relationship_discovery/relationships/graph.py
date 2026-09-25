from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from market_relationship_discovery.relationships.catalog import RelationshipDefinition


@dataclass(frozen=True, slots=True)
class RelationshipEdge:
    name: str
    source_symbols: tuple[str, ...]
    target: str
    formula: str


class RelationshipGraph:
    def __init__(self, definitions: Sequence[RelationshipDefinition]) -> None:
        self._definitions = tuple(definitions)

    @classmethod
    def from_definitions(cls, definitions: Sequence[RelationshipDefinition]) -> RelationshipGraph:
        unique: dict[tuple[str, str, str], RelationshipDefinition] = {}
        for definition in definitions:
            unique[(definition.name, definition.target, definition.formula)] = definition
        return cls(tuple(unique.values()))

    @property
    def nodes(self) -> tuple[str, ...]:
        nodes = {definition.target for definition in self._definitions}
        for definition in self._definitions:
            nodes.update(definition.dependencies())
        return tuple(sorted(nodes))

    @property
    def edges(self) -> tuple[RelationshipEdge, ...]:
        return tuple(
            RelationshipEdge(
                name=definition.name,
                source_symbols=tuple(sorted(definition.dependencies())),
                target=definition.target,
                formula=definition.formula,
            )
            for definition in self._definitions
        )

    def expand(
        self, seeds: Sequence[str], *, max_depth: int = 1
    ) -> tuple[RelationshipDefinition, ...]:
        if max_depth < 0:
            raise ValueError("max_depth cannot be negative")
        reachable = {str(symbol).upper() for symbol in seeds if str(symbol).strip()}
        found: list[RelationshipDefinition] = []
        used: set[tuple[str, str, str]] = set()
        for _ in range(max_depth):
            current_reachable = set(reachable)
            additions: list[RelationshipDefinition] = []
            for definition in self._definitions:
                key = (definition.name, definition.target, definition.formula)
                if key in used:
                    continue
                dependencies = {dependency.upper() for dependency in definition.dependencies()}
                if dependencies <= current_reachable:
                    additions.append(definition)
                    used.add(key)
                    found.append(definition)
            if not additions:
                break
            reachable.update(definition.target.upper() for definition in additions)
        return tuple(found)
