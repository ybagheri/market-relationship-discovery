import numpy as np
import pandas as pd

from market_relationship_discovery.discovery.engine import (
    CandidateDiscoveryEngine,
    CandidateStatus,
    DiscoveryCandidate,
)
from market_relationship_discovery.discovery.evaluator import GraphCandidateEvaluator
from market_relationship_discovery.discovery.graph import GraphRelationshipDiscoveryEngine
from market_relationship_discovery.relationships.catalog import RelationshipDefinition
from market_relationship_discovery.relationships.formula import FormulaParser
from market_relationship_discovery.relationships.graph import RelationshipGraph


def test_a_hyphenated_broker_name_survives_candidate_generation() -> None:
    """A broker name containing a hyphen must stay one dependency.

    The engine interpolates live broker names into formula text. Written bare,
    ``XAU-USD`` reads as a subtraction, so the generated candidate would ask for
    a symbol that does not exist in the panel and could never be evaluated.
    """
    candidates = CandidateDiscoveryEngine().generate(["XAU-USD", "EURUSD"], minimum_observations=0)

    assert candidates
    for candidate in candidates:
        assert FormulaParser.parse(candidate.formula).dependencies() <= {"XAU-USD", "EURUSD"}


def test_generated_candidates_do_not_depend_on_a_symbol_that_cannot_exist() -> None:
    candidates = CandidateDiscoveryEngine().generate(["XAU-USD", "EURUSD"], minimum_observations=0)

    dependencies = {
        symbol
        for candidate in candidates
        for symbol in FormulaParser.parse(candidate.formula).dependencies()
    }

    assert "XAU" not in dependencies
    assert "USD" not in dependencies


def test_an_unspaced_subtraction_generates_a_dependent_relationship() -> None:
    """``A-B`` is a subtraction, so both operands are real dependencies."""
    graph = RelationshipGraph.from_definitions(
        (RelationshipDefinition("SPREAD_SYNTHETIC", "EURUSD_SPREAD", "EURUSD-GBPUSD"),)
    )

    candidates = GraphRelationshipDiscoveryEngine(graph, max_depth=1).discover(["EURUSD", "GBPUSD"])

    assert len(candidates) == 1
    assert FormulaParser.parse(candidates[0].formula).dependencies() == {
        "EURUSD",
        "GBPUSD",
    }


def test_a_hyphenated_panel_column_is_evaluable_end_to_end() -> None:
    """The evaluator resolves a quoted dependency against the real column."""
    index = pd.date_range("2026-09-25", periods=60, freq="h", tz="UTC")
    gold = np.linspace(2000.0, 2010.0, 60)
    eurusd = np.linspace(1.1, 1.2, 60)
    prices = pd.DataFrame(
        {"XAU-USD": gold, "EURUSD": eurusd, "GOLD_EUR": gold / eurusd}, index=index
    )
    candidate = DiscoveryCandidate(
        name="GOLD_EUR_SYNTHETIC",
        target="GOLD_EUR",
        formula='"XAU-USD" / EURUSD',
        status=CandidateStatus.RESEARCH_CANDIDATE,
    )

    evaluated = GraphCandidateEvaluator().evaluate(prices, [candidate], minimum_observations=30)

    assert len(evaluated) == 1
    summary = evaluated[0].summary
    assert summary["status"] == CandidateStatus.REQUIRES_FURTHER_VALIDATION.value
    assert not summary.get("missing_symbols")
    assert summary["observations"] == 60


def test_an_unquoted_hyphenated_name_is_reported_as_a_missing_symbol() -> None:
    """The failure mode the quoting prevents is reported, not silently passed."""
    index = pd.date_range("2026-09-25", periods=60, freq="h", tz="UTC")
    gold = np.linspace(2000.0, 2010.0, 60)
    eurusd = np.linspace(1.1, 1.2, 60)
    prices = pd.DataFrame(
        {"XAU-USD": gold, "EURUSD": eurusd, "GOLD_EUR": gold / eurusd}, index=index
    )
    candidate = DiscoveryCandidate(
        name="GOLD_EUR_SYNTHETIC",
        target="GOLD_EUR",
        formula="XAU-USD / EURUSD",
        status=CandidateStatus.RESEARCH_CANDIDATE,
    )

    evaluated = GraphCandidateEvaluator().evaluate(prices, [candidate], minimum_observations=30)

    assert evaluated[0].summary["status"] == CandidateStatus.REQUIRES_DATA.value
    assert evaluated[0].summary["missing_symbols"] == ["USD", "XAU"]
