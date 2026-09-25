from dataclasses import dataclass

from market_relationship_discovery.relationships.formula import FormulaParser


@dataclass(frozen=True, slots=True)
class RelationshipDefinition:
    name: str
    target: str
    formula: str
    classification: str = "research_candidate"

    def dependencies(self) -> set[str]:
        return FormulaParser.parse(self.formula).dependencies()


INITIAL_RELATIONSHIPS = (
    RelationshipDefinition("EURGBP_SYNTHETIC", "EURGBP", "EURUSD / GBPUSD"),
    RelationshipDefinition("EURJPY_SYNTHETIC", "EURJPY", "EURUSD * USDJPY"),
    RelationshipDefinition("GBPJPY_SYNTHETIC", "GBPJPY", "GBPUSD * USDJPY"),
    RelationshipDefinition("XAUEUR_SYNTHETIC", "XAUEUR", "XAUUSD / EURUSD"),
    RelationshipDefinition("GOLD_SILVER_RATIO", "GOLD_SILVER_RATIO", "XAUUSD / XAGUSD"),
)


class RelationshipCatalog:
    def __init__(
        self, definitions: tuple[RelationshipDefinition, ...] = INITIAL_RELATIONSHIPS
    ) -> None:
        self._definitions = definitions

    def all(self) -> tuple[RelationshipDefinition, ...]:
        return self._definitions

    def required_symbols(self) -> set[str]:
        return {symbol for definition in self._definitions for symbol in definition.dependencies()}
