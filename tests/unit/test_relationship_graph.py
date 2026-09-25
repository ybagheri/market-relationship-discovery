from market_relationship_discovery.discovery.graph import GraphRelationshipDiscoveryEngine
from market_relationship_discovery.relationships.catalog import RelationshipDefinition
from market_relationship_discovery.relationships.graph import RelationshipGraph

DEFINITIONS = (
    RelationshipDefinition("A", "A2", "A"),
    RelationshipDefinition("B", "B2", "A2 * B"),
    RelationshipDefinition("C", "C2", "B2 + A"),
)


def test_graph_nodes_and_edges_are_deterministic() -> None:
    graph = RelationshipGraph.from_definitions(DEFINITIONS + DEFINITIONS[:1])

    assert graph.nodes == ("A", "A2", "B", "B2", "C2")
    assert graph.edges[0].source_symbols == ("A",)


def test_graph_expands_two_hops() -> None:
    graph = RelationshipGraph.from_definitions(DEFINITIONS)

    assert [item.name for item in graph.expand(["A", "B"], max_depth=1)] == ["A"]
    assert [item.name for item in graph.expand(["A", "B"], max_depth=2)] == ["A", "B"]
    assert [item.name for item in graph.expand(["A", "B"], max_depth=3)] == ["A", "B", "C"]
    assert graph.expand(["A"], max_depth=0) == ()


def test_graph_stops_on_cycles() -> None:
    graph = RelationshipGraph.from_definitions(
        (
            RelationshipDefinition("A", "B", "A"),
            RelationshipDefinition("B", "A", "B"),
        )
    )

    assert [item.name for item in graph.expand(["A"], max_depth=5)] == ["A", "B"]


def test_graph_discovery_returns_catalog_candidates() -> None:
    candidates = GraphRelationshipDiscoveryEngine().discover(["EURUSD", "GBPUSD"])

    assert [candidate.name for candidate in candidates] == ["EURGBP_SYNTHETIC"]
