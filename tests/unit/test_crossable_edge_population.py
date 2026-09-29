"""A "crossable" figure must describe the rows that were actually crossable.

`maximum_gross_crossable_edge` and `maximum_net_crossable_edge` were read from
the whole aligned frame and gated only on the contract check, while
`crossable_observations` beside them was counted from the frame filtered by
`is_crossable` — which the execution verdict also forces to false. The two
fields therefore described different populations: the maximum over every aligned
row, and the count over the rows a position could actually be taken on.

That let a run report a positive maximum crossable edge next to
`crossable_observations = 0`. Both figures were individually correct and they
were placed in the same record, which is what makes the pair readable as one
statement about the same set of rows. Nothing errored, because each field was
computed exactly as written.

The invariant is now that an empty crossable population reports no maximum at
all, rather than the maximum of rows nothing was crossable on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from market_relationship_discovery.market_data.contract import ContractSpecification
from market_relationship_discovery.market_data.cross_broker import (
    ComparisonKind,
    CrossBrokerComparisonEngine,
    CrossBrokerRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def feeds() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two feeds that genuinely disagree, on a grid the aligner can match."""
    index = pd.date_range("2026-09-25", periods=40, freq="s", tz="UTC")
    left = pd.DataFrame(
        {
            "timestamp": index,
            "broker": "A",
            "symbol": "EURUSD",
            "bid": [1.1000] * 40,
            "ask": [1.1002] * 40,
        }
    )
    right = pd.DataFrame(
        {
            "timestamp": index + pd.Timedelta(milliseconds=5),
            "broker": "B",
            "symbol": "EURUSD",
            "bid": [1.0900] * 40,
            "ask": [1.0902] * 40,
        }
    )
    return left, right


def contracts() -> tuple[ContractSpecification, ContractSpecification]:
    """A pair that is contract-compatible but not executable at this size.

    `volume_max == volume_step` means any requested size rounds down to a single
    step, so the fill ratio can never clear a 0.9 threshold. The contracts
    themselves agree, so this exercises the execution verdict rather than the
    contract gate, which is the state the defect needed.
    """
    base = json.loads(
        (REPO_ROOT / "examples" / "broker_a_contract.json").read_text(encoding="utf-8")
    )
    base["broker"] = "A"
    base["volume_min"] = 0.01
    base["volume_max"] = 0.10
    base["volume_step"] = 0.10
    other = dict(base)
    other["broker"] = "B"
    other["server"] = "DemoServerB"
    return ContractSpecification.from_dict(base), ContractSpecification.from_dict(other)


def request(**overrides: object) -> CrossBrokerRequest:
    parameters: dict[str, object] = {
        "broker_a": "A",
        "broker_b": "B",
        "symbol": "EURUSD",
        "comparison_kind": ComparisonKind.TICK,
        "max_alignment_delay_ms": 100,
        "volume": 0.01,
        "minimum_fill_ratio": 0.9,
    }
    parameters.update(overrides)
    return CrossBrokerRequest(**parameters)  # type: ignore[arg-type]


def test_an_edge_is_never_reported_for_an_empty_crossable_population() -> None:
    """The pair must be readable as one statement about the same rows.

    This is the contradiction the defect produced: a positive
    `maximum_gross_crossable_edge` of 0.0098 beside
    `crossable_observations = 0`, on feeds that disagree by far more than the
    spread, where the execution verdict blocked the position.
    """
    left, right = feeds()
    contract_a, contract_b = contracts()

    summary = (
        CrossBrokerComparisonEngine()
        .compare(left, right, request(contract_a=contract_a, contract_b=contract_b))
        .summary
    )

    # Precondition: this input really does block on execution, and the feeds
    # really do disagree. Without both, the assertion below would be vacuous.
    assert summary.crossable_observations == 0
    assert summary.opportunity_count == 0
    assert summary.maximum_absolute_price_difference > 0.009

    assert summary.maximum_gross_crossable_edge is None
    assert summary.maximum_net_crossable_edge is None


def test_a_crossable_population_still_reports_its_own_maximum() -> None:
    """The other half: a real edge is still reported, and is not over-suppressed.

    The fix reads from the crossable rows rather than all aligned rows, so a
    run that genuinely is executable must be unaffected.
    """
    left, right = feeds()
    base = json.loads(
        (REPO_ROOT / "examples" / "broker_a_contract.json").read_text(encoding="utf-8")
    )
    base["broker"] = "A"
    base["volume_min"] = 0.01
    base["volume_max"] = 100.0
    base["volume_step"] = 0.01
    contract_a = ContractSpecification.from_dict(base)
    other = dict(base)
    other["broker"] = "B"
    other["server"] = "DemoServerB"
    contract_b = ContractSpecification.from_dict(other)

    summary = (
        CrossBrokerComparisonEngine()
        .compare(left, right, request(contract_a=contract_a, contract_b=contract_b))
        .summary
    )

    assert summary.crossable_observations > 0
    assert summary.maximum_gross_crossable_edge is not None
    assert summary.maximum_gross_crossable_edge > 0


def test_the_reported_maximum_comes_from_the_crossable_rows() -> None:
    """Not merely non-null: the value must be the crossable rows' own maximum.

    Reading `aligned` produced a well-formed number in the common case too, so
    the previous test alone would not have caught the wrong source.
    """
    left, right = feeds()
    analysis = CrossBrokerComparisonEngine().compare(left, right, request())

    summary = analysis.summary
    aligned = analysis.aligned_observations
    crossable = aligned[aligned["is_crossable"]]

    assert len(crossable) == summary.crossable_observations
    if len(crossable):
        assert summary.maximum_gross_crossable_edge == pytest.approx(
            float(crossable["gross_crossable_edge"].max())
        )
        assert summary.maximum_net_crossable_edge == pytest.approx(
            float(crossable["net_crossable_edge"].max())
        )


def test_a_blocked_contract_reports_no_edge() -> None:
    """The contract gate is unchanged: a blocked pair reports no maximum."""
    left, right = feeds()
    base = json.loads(
        (REPO_ROOT / "examples" / "broker_a_contract.json").read_text(encoding="utf-8")
    )
    base["broker"] = "A"
    # A tick value an order of magnitude away makes the legs incomparable.
    incompatible = dict(base)
    incompatible["broker"] = "B"
    incompatible["server"] = "DemoServerB"
    incompatible["tick_value"] = 10.0
    contract_a = ContractSpecification.from_dict(base)
    contract_b = ContractSpecification.from_dict(incompatible)

    summary = (
        CrossBrokerComparisonEngine()
        .compare(
            left,
            right,
            request(contract_a=contract_a, contract_b=contract_b),
        )
        .summary
    )

    assert summary.crossable_observations == 0
    assert summary.maximum_gross_crossable_edge is None
    assert summary.maximum_net_crossable_edge is None
