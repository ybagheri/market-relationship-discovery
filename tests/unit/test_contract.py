from dataclasses import replace

from market_relationship_discovery.market_data.contract import (
    ContractCompatibilityStatus,
    ContractSpecification,
    ContractSpecificationAnalyzer,
)


def specification(**overrides: object) -> ContractSpecification:
    values: dict[str, object] = {
        "broker": "BrokerA",
        "server": "ServerA",
        "symbol": "EURUSD",
        "description": "EURUSD",
        "path": "Forex\\EURUSD",
        "currency_base": "EUR",
        "currency_profit": "USD",
        "digits": 5,
        "point": 0.00001,
        "spread": 10,
        "trade_mode": 4,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "margin_initial": 0.0,
    }
    values.update(overrides)
    return ContractSpecification(**values)


def test_missing_specifications_are_unverified() -> None:
    report = ContractSpecificationAnalyzer().compare(None, None)

    assert report.status is ContractCompatibilityStatus.UNVERIFIED
    assert report.issues


def test_identical_specifications_are_compatible() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", server="ServerB", spread=12),
    )

    assert report.status is ContractCompatibilityStatus.COMPATIBLE
    assert report.issues == ()
    assert report.contract_size_ratio == 1.0


def test_contract_size_difference_requires_normalization() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", contract_size=50000.0),
    )

    assert report.status is ContractCompatibilityStatus.NORMALIZATION_REQUIRED
    assert report.contract_size_ratio == 0.5


def test_currency_difference_is_incompatible() -> None:
    report = ContractSpecificationAnalyzer().compare(
        specification(),
        replace(specification(), broker="BrokerB", currency_profit="GBP"),
    )

    assert report.status is ContractCompatibilityStatus.INCOMPATIBLE
    assert "profit currencies differ" in report.issues
