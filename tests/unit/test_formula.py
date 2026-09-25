import pytest

from market_relationship_discovery.relationships.formula import FormulaParser, Operation


def test_parser_respects_precedence() -> None:
    expression = FormulaParser.parse("A * B / C")

    assert expression.operation is Operation.DIVIDE
    assert expression.left is not None
    assert expression.left.operation is Operation.MULTIPLY
    assert expression.dependencies() == {"A", "B", "C"}


@pytest.mark.parametrize("formula", ["", "A +", "A B", "(A / B", "A / B)"])
def test_parser_rejects_invalid_formulas(formula: str) -> None:
    with pytest.raises(ValueError):
        FormulaParser.parse(formula)
