"""The generated candidate family: what it claims, and what it costs.

Two defects lived here. The observation gate relabelled candidates that had
never been evaluated as candidates whose data had been measured and found too
short, and the three-symbol family grew as n(n-1)(n-2) with no bound, so a wide
catalog produced a family whose size is itself a research finding.
"""

from market_relationship_discovery.application.commands import discover_relationships
from market_relationship_discovery.discovery.engine import (
    CandidateDiscoveryEngine,
    CandidateStatus,
    DiscoveryCandidate,
)
from market_relationship_discovery.discovery.evaluator import GraphCandidateEvaluator


def _evaluated(name: str, observations: int) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        name=name,
        target=name,
        formula="EURUSD / GBPUSD",
        status=CandidateStatus.REQUIRES_FURTHER_VALIDATION,
        observations=observations,
    )


def test_an_unevaluated_candidate_is_not_reported_as_judged_on_its_data() -> None:
    """`requires_data` must not become `insufficient_observations`.

    The second is a claim that the candidate was evaluated and the panel held too
    few rows. The first is a claim that no evaluation happened. The gate
    conflated them, so every freshly generated candidate was reported as having
    been measured and rejected.
    """
    generated = CandidateDiscoveryEngine().generate(["EURUSD", "GBPUSD"])

    assert {candidate.status for candidate in generated.candidates} == {
        CandidateStatus.REQUIRES_DATA
    }


def test_the_gate_still_applies_to_a_candidate_that_was_evaluated() -> None:
    short = CandidateDiscoveryEngine().filter(_evaluated("A", 5), minimum_observations=30)
    long_enough = CandidateDiscoveryEngine().filter(_evaluated("B", 40), minimum_observations=30)

    assert short.status is CandidateStatus.INSUFFICIENT_OBSERVATIONS
    assert short.observations == 5
    assert long_enough.status is CandidateStatus.REQUIRES_FURTHER_VALIDATION


def test_the_family_is_bounded_and_reports_what_the_bound_removed() -> None:
    family = CandidateDiscoveryEngine().generate(
        [f"SYM{index}" for index in range(12)], maximum_candidates=20
    )

    assert len(family.candidates) == 20
    assert family.is_truncated is True
    assert family.removed_count == family.generated - 20
    assert family.generated == 12 * 11 + 12 * 11 * 10
    assert family.to_dict()["family_truncated"] is True


def test_the_three_symbol_family_does_not_grow_unbounded() -> None:
    """A wide catalog must not produce a combinatorial family by default."""
    family = CandidateDiscoveryEngine().generate([f"SYM{index}" for index in range(40)])

    assert len(family.candidates) <= 500
    assert family.removed_count > 0


def test_a_bound_of_one_keeps_the_family_deterministic() -> None:
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    first = CandidateDiscoveryEngine().generate(symbols, maximum_candidates=1)
    second = CandidateDiscoveryEngine().generate(symbols, maximum_candidates=1)

    assert [c.name for c in first.candidates] == [c.name for c in second.candidates]


def test_a_zero_bound_is_rejected_rather_than_silently_empty() -> None:
    try:
        CandidateDiscoveryEngine().generate(["EURUSD"], maximum_candidates=0)
    except ValueError as exc:
        assert "maximum_candidates" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("a zero bound should not silently return no candidates")


def test_a_generated_target_is_declared_synthetic() -> None:
    """A minted target name is not a column a broker publishes.

    Reporting these candidates as merely awaiting observations is what inflated
    the requires_data count: the evaluator looks for a column that cannot exist.
    """
    candidates = CandidateDiscoveryEngine().generate(["EURUSD", "GBPUSD"]).candidates

    assert all(candidate.target_is_synthetic for candidate in candidates)
    assert all(candidate.target.startswith("SYNTH_") for candidate in candidates)


def test_the_cli_payload_states_that_a_generated_target_is_not_a_column() -> None:
    payload = discover_relationships(["EURUSD", "GBPUSD"], 100)

    assert "synthetic" in payload["target_note"]
    assert payload["family"]["candidates"] == len(payload["candidates"])


def test_a_candidate_whose_target_is_absent_reports_the_missing_column() -> None:
    """The synthetic target is missing data, not too little of it."""
    import pandas as pd

    prices = pd.DataFrame({"EURUSD": [1.1, 1.2], "GBPUSD": [1.3, 1.4]})
    candidate = DiscoveryCandidate(
        name="SYNTH_EURUSD_DIV_GBPUSD_RATIO",
        target="SYNTH_EURUSD_DIV_GBPUSD",
        formula="EURUSD / GBPUSD",
        status=CandidateStatus.REQUIRES_DATA,
        target_is_synthetic=True,
    )

    evaluated = GraphCandidateEvaluator().evaluate(prices, [candidate], minimum_observations=30)

    assert evaluated[0].summary["status"] == CandidateStatus.REQUIRES_DATA.value
    assert evaluated[0].summary["missing_symbols"] == ["SYNTH_EURUSD_DIV_GBPUSD"]
